"""Step 5: monitoring. Visits approved sources, collects only new/changed content, de-duplicates, stores
evidence with links, and keeps a per-source check history."""
import difflib
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from ..fetch import (domain, extract_main_text, fetch, jaccard, normalize_url, page_links, robots_allowed, sha,
                     shingles)
from ..models import Company, Document, Source, SourceCheck, now
from ..search import gdelt_search, news_search, parse_feed

log = logging.getLogger("crawler")
MAX_NEW_PER_SOURCE = 8


class _Dedup:
    def __init__(self, db: Session, company_id: int):
        since = now() - timedelta(days=90)
        rows = db.query(Document.id, Document.url_hash, Document.content_hash, Document.text, Document.url) \
            .filter(Document.company_id == company_id, Document.fetched_at >= since).all()
        self.urls = {r.url_hash for r in db.query(Document.url_hash).filter(Document.company_id == company_id)}
        self.hashes = {r.content_hash: r.id for r in rows}
        self.sh = [(r.id, shingles(r.text[:4000]), domain(r.url)) for r in rows if r.text]

    def check(self, url: str, text: str):
        """-> ('url'|'exact'|'near'|None, original_doc_id)"""
        if sha(normalize_url(url)) in self.urls:
            return "url", None
        h = sha(" ".join(text.split()).lower())
        if h in self.hashes:
            return "exact", self.hashes[h]
        s = shingles(text[:4000])
        if len(s) > 20:
            for did, other, _ in self.sh:
                if jaccard(s, other) >= 0.6:
                    return "near", did
        return None, None

    def add(self, doc: Document):
        self.urls.add(doc.url_hash)
        self.hashes[doc.content_hash] = doc.id
        if doc.text:
            self.sh.append((doc.id, shingles(doc.text[:4000]), domain(doc.url)))


def _article_text(url: str, fallback: str) -> tuple[str, str, datetime | None, bool]:
    """Fetch the original article if robots allows it; otherwise keep the feed/search snippet."""
    if not robots_allowed(url):
        return "", fallback, None, False
    r = fetch(url)
    if not r.ok or "html" not in r.content_type:
        return "", fallback, None, False
    title, text, pub = extract_main_text(r.text, r.url)
    if len(text) < 200:
        return title, fallback or text, pub, False
    return title, text[:20000], pub, True


def _store(db, company, source, dd: _Dedup, *, url, title, text, published, publisher, full, job_id, stats):
    text = (text or "").strip()
    if not text and not title:
        return None
    kind, orig = dd.check(url, f"{title}\n{text}")
    if kind == "url":
        stats["duplicates"] += 1
        return None
    doc = Document(company_id=company.id, source_id=source.id, url=url, url_hash=sha(normalize_url(url)),
                   title=(title or "")[:1000], publisher=publisher[:300], published_at=published,
                   content_hash=sha(" ".join(f"{title}\n{text}".split()).lower()), text=text, full_text=full,
                   job_id=job_id)
    if kind in ("exact", "near"):
        doc.duplicate_of, doc.analyzed = orig, True  # kept as corroboration evidence, not re-analysed
        stats["duplicates"] += 1
    db.add(doc)
    db.flush()
    dd.add(doc)
    if not doc.duplicate_of:
        stats["new"] += 1
    return doc


def _crawl_items(db, company, source, dd, items, lookback, job_id, stats):
    cutoff = now() - timedelta(days=lookback)
    fresh = []
    for it in items:
        if not it.get("url"):
            continue
        if it.get("published") and it["published"] < cutoff:
            stats["too_old"] += 1
            continue
        if sha(normalize_url(it["url"])) in dd.urls:
            stats["duplicates"] += 1
            continue
        fresh.append(it)
    fresh.sort(key=lambda x: x.get("published") or datetime.min, reverse=True)
    for it in fresh[:MAX_NEW_PER_SOURCE]:
        t, text, pub, full = _article_text(it["url"], f"{it.get('title', '')}. {it.get('snippet', '')}")
        _store(db, company, source, dd, url=it["url"], title=it.get("title") or t, text=text,
               published=it.get("published") or pub, publisher=it.get("publisher") or domain(it["url"]),
               full=full, job_id=job_id, stats=stats)


def crawl_source(db: Session, company: Company, source: Source, dd: _Dedup, lookback: int, job_id=None) -> dict:
    stats = {"seen": 0, "new": 0, "duplicates": 0, "too_old": 0, "changed": False}
    status, http_status, msg = "ok", None, ""
    try:
        if source.kind == "news_query":
            tl = "w" if lookback <= 7 else "m"
            items = news_search(source.query, 15, timelimit=tl)
            items += gdelt_search(source.query.replace('"', ""), 15, timespan=f"{min(lookback, 90)}d")
            uniq = {normalize_url(i["url"]): i for i in items}
            stats["seen"] = len(uniq)
            _crawl_items(db, company, source, dd, list(uniq.values()), lookback, job_id, stats)
            if not uniq:
                msg = "No results from news indexes for this query"
        elif source.kind == "rss":
            r = fetch(source.url)
            http_status = r.status
            if r.blocked:
                status, msg = "blocked", r.error
            elif not r.ok:
                status, msg = "dead" if (r.status or 0) in (404, 410) or r.status is None else "error", r.error
            else:
                items = parse_feed(r.text)
                stats["seen"] = len(items)
                _crawl_items(db, company, source, dd, items, lookback, job_id, stats)
        elif source.kind == "web":
            r = fetch(source.url)
            http_status = r.status
            if r.blocked:
                status, msg = "blocked", r.error
            elif not r.ok:
                status, msg = "dead" if (r.status or 0) in (404, 410) or r.status is None else "error", r.error
            else:
                title, text, pub = extract_main_text(r.text, r.url)
                h = sha(" ".join(text.split()))
                if source.page_hash and h != source.page_hash:
                    # change detection: store only what was added/changed on the page
                    prev = db.query(Document).filter(Document.source_id == source.id).order_by(Document.id.desc()).first()
                    old_lines = (prev.text if prev and prev.title.startswith("Snapshot") else "").splitlines()
                    added = [l[2:] for l in difflib.ndiff(old_lines, text.splitlines()) if l.startswith("+ ") and len(l) > 25]
                    if added:
                        stats["changed"] = True
                        _store(db, company, source, dd, url=r.url + f"#change-{now():%Y%m%d%H%M}",
                               title=f"Change detected on {source.name}", text="\n".join(added)[:8000],
                               published=now(), publisher=domain(r.url), full=True, job_id=job_id, stats=stats)
                # keep a snapshot as the baseline for the next diff (not analysed as news)
                db.add(Document(company_id=company.id, source_id=source.id, url=r.url + f"#snapshot-{now():%Y%m%d%H%M%S}",
                                url_hash=sha(r.url + str(now())), title=f"Snapshot of {source.name}",
                                content_hash=h, text=text[:30000], full_text=True, analyzed=True, relevant=False,
                                publisher=domain(r.url), job_id=job_id))
                source.page_hash = h
                # listing pages: follow new article links on the same site
                links = [(u, t) for u, t in page_links(r.text, r.url)
                         if domain(u) == domain(r.url) and len(t) > 30 and urlparse(u).path.count("/") >= 2
                         and normalize_url(u) != normalize_url(r.url)]
                uniq = list({normalize_url(u): (u, t) for u, t in links}.values())
                stats["seen"] = len(uniq)
                items = [{"url": u, "title": t, "snippet": "", "published": None} for u, t in uniq[:25]]
                _crawl_items(db, company, source, dd, items, lookback, job_id, stats)
    except Exception as e:  # one bad source must not stop the run
        log.exception("source %s failed", source.id)
        status, msg = "error", f"{type(e).__name__}: {e}"[:500]

    source.last_checked = now()
    if status == "ok":
        source.health, source.fail_count, source.last_error = "ok", 0, ""
        if stats["new"]:
            source.last_new_item = now()
        source.total_items += stats["new"]
    else:
        source.health, source.fail_count, source.last_error = status, source.fail_count + 1, msg
    db.add(SourceCheck(source_id=source.id, job_id=job_id, status=status, http_status=http_status,
                       items_seen=stats["seen"], new_items=stats["new"], duplicates=stats["duplicates"],
                       changed=stats["changed"], message=msg or (f"{stats['too_old']} items older than lookback" if stats["too_old"] else "")))
    db.commit()
    return {**stats, "status": status}


def crawl_company(db: Session, company: Company, progress=lambda m: None, job_id=None, lookback: int | None = None) -> dict:
    lookback = lookback or company.settings.get("lookback_days", 30)
    sources = db.query(Source).filter(Source.company_id == company.id, Source.status == "approved",
                                      Source.kind != "upload").all()
    dd = _Dedup(db, company.id)
    totals = {"sources": len(sources), "new_documents": 0, "duplicates": 0, "failed_sources": 0, "changed_pages": 0}
    for i, s in enumerate(sources, 1):
        progress(f"Crawling {i}/{len(sources)}: {s.name}")
        r = crawl_source(db, company, s, dd, lookback, job_id)
        totals["new_documents"] += r["new"]
        totals["duplicates"] += r["duplicates"]
        totals["failed_sources"] += r["status"] != "ok"
        totals["changed_pages"] += bool(r["changed"])
    if company.stage == "stack_ready":
        company.stage = "monitoring"
    db.commit()
    return totals
