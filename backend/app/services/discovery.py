"""Step 4: build the Signal Stack. Nothing is hard-coded per company: competitors and sources are found with
web search, probed (robots.txt, liveness, feed, freshness) and justified (Specific / Recent / Credible)."""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from ..fetch import domain, extract_main_text, fetch, find_feeds, normalize_url, page_links, robots_allowed
from ..llm import complete_json
from ..models import Company, Competitor, ProfileFact, Source
from ..search import parse_feed, web_search
from .research import profile_text

log = logging.getLogger("discovery")
SOCIAL = ("facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com", "youtube.com", "tiktok.com",
          "pinterest.", "wikipedia.org", "crunchbase.com", "zoominfo", "glassdoor", "ambitionbox")


# ---------------------------------------------------------------- competitors

def discover_competitors(db: Session, company: Company, progress=lambda m: None, extra_round: bool = False) -> list[Competitor]:
    prof = profile_text(db, company)
    known = [c.name for c in db.query(Competitor).filter(Competitor.company_id == company.id)]
    founder_named = [f.value for f in db.query(ProfileFact).filter(
        ProfileFact.company_id == company.id, ProfileFact.field == "competitors").all()]
    kw = company.keywords[:3] or [company.industry]
    queries = [f"{company.name} competitors", f"{company.name} alternatives",
               f"best {kw[0]} companies", f"top {company.industry} platforms"]
    if len(kw) > 1:
        queries.append(f"{kw[1]} companies")
    if extra_round:  # widen the net: alternatives to the competitors already found, and substitutes
        queries = [f"{n} alternatives" for n in known[:3]] + [f"{kw[-1]} startups", f"{company.industry} substitutes"]
    results = []
    for q in queries:
        progress(f"Searching: {q}")
        results += [dict(r, query=q) for r in web_search(q, 8)]
    own = domain(company.website)
    results = [r for r in results if domain(r["url"]) != own]
    listing = "\n".join(f"- {r['url']} | {r['title']} | {r['snippet'][:220]}" for r in results[:45])

    progress("Selecting competitors")
    data = complete_json(
        f"""{prof}

Founder-named competitors/substitutes (highest priority, include them): {founder_named or "none given"}

Web search results about this company's competitive landscape:
{listing}

{"Already tracked (do NOT repeat): " + ", ".join(known) if known else ""}
Identify 7-10 real competitors or substitutes that matter to THIS company (same customers, same problem).
Include direct competitors and important substitutes (e.g. DIY alternatives, adjacent players). Only include
organisations that appear in the search results or were named by the founder. Do not include the company itself
or pure directories/media sites.
Return JSON: {{"competitors": [{{"name": "...", "website": "https://... (homepage if known from results, else empty)",
"kind": "direct|substitute|indirect", "description": "what they do (1 sentence)",
"why_relevant": "why their moves matter to {company.name} specifically (1-2 sentences)",
"evidence_url": "a result URL that mentions them, or 'founder'"}}]}}""",
        max_tokens=4000,
    )
    cands = [c for c in data.get("competitors", []) if (c.get("name") or "").strip()]
    # second, independent check: does each candidate really serve the same customers / problem?
    if cands:
        check = complete_json(
            f"""Company: {company.name} - {company.summary}
For each candidate, answer whether it genuinely competes for the SAME customers or solves the SAME problem
(directly or as a realistic substitute). Reject unrelated organisations, media sites, directories and tools that
merely appeared in search results.
Candidates: {[{"name": c["name"], "description": c.get("description", "")} for c in cands]}
Return JSON: {{"verdicts": [{{"name": "...", "keep": true/false, "why": "..."}}]}}""", max_tokens=1500)
        rejected = {v["name"].lower() for v in check.get("verdicts", []) if not v.get("keep")}
        cands = [c for c in cands if c["name"].lower() not in rejected]
    existing = {c.name.lower(): c for c in db.query(Competitor).filter(Competitor.company_id == company.id).all()}
    out = []
    for c in cands[:10]:
        name = (c.get("name") or "").strip()
        if not name or name.lower() == company.name.lower():
            continue
        site = (c.get("website") or "").strip()
        if not site or domain(site) in ("", own):
            progress(f"Finding website of {name}")
            hits = [h for h in web_search(f"{name} official website", 5)
                    if not any(s in h["url"] for s in SOCIAL)]
            site = f"https://{urlparse(hits[0]['url']).netloc}" if hits else ""
        if site:
            site = f"{urlparse(site).scheme or 'https'}://{urlparse(site).netloc or site}"
        comp = existing.get(name.lower()) or Competitor(company_id=company.id, name=name)
        comp.website, comp.kind = site, c.get("kind", "direct")
        comp.description, comp.why_relevant = c.get("description", ""), c.get("why_relevant", "")
        comp.evidence_url = c.get("evidence_url", "")
        if comp.status == "removed" and name.lower() in existing:
            continue
        comp.status = "approved"
        db.add(comp)
        out.append(comp)
    db.commit()
    return out


# ---------------------------------------------------------------- probing

def probe(url: str) -> dict:
    """Check a candidate source: robots, liveness, RSS/Atom feed, freshness."""
    info = {"url": url, "allowed": True, "ok": False, "feed": "", "latest": None, "title": "", "status": None,
            "error": "", "kind": "web", "items": 0}
    if not robots_allowed(url):
        info.update(allowed=False, error="robots.txt disallows crawling")
        return info
    r = fetch(url)
    info["status"] = r.status
    if not r.ok:
        info["error"] = r.error or f"HTTP {r.status}"
        return info
    info["ok"] = True
    body = r.text
    if "xml" in r.content_type or body.lstrip().startswith(("<?xml", "<rss", "<feed")):
        items = parse_feed(body)
        if items:
            info.update(kind="rss", feed=r.url, items=len(items),
                        latest=max((i["published"] for i in items if i["published"]), default=None))
            info["title"] = re.search(r"<title[^>]*>(.*?)</title>", body, re.S).group(1)[:200] if "<title" in body else ""
            return info
    title, text, pub = extract_main_text(body, r.url)
    info["title"], info["latest"] = title, pub
    feeds = find_feeds(body, r.url)
    for f in feeds[:2]:
        if domain(f) != domain(r.url) or not robots_allowed(f):
            continue
        fr = fetch(f)
        items = parse_feed(fr.text) if fr.ok else []
        if items:
            info.update(kind="rss", feed=fr.url, items=len(items),
                        latest=max((i["published"] for i in items if i["published"]), default=None))
            break
    if info["kind"] == "web":
        # listing pages: count article-like links as a freshness proxy
        info["items"] = sum(1 for h, t in page_links(body, r.url)
                            if domain(h) == domain(r.url) and urlparse(h).path.count("/") >= 2 and len(t) > 25)
    return info


def _recency_score(latest: datetime | None, kind: str) -> float:
    if latest is None:
        return 0.5 if kind == "news_query" else 0.35
    age = (datetime.utcnow() - latest).days
    return 1.0 if age <= 14 else 0.8 if age <= 45 else 0.5 if age <= 120 else 0.2


# ---------------------------------------------------------------- sources

def _add_source(db, company, seen, *, category, kind, name, url, reason, specific, recent, credible,
                query="", competitor_id=None, status=None, discovered_by="discovery"):
    key = normalize_url(url) if kind != "news_query" else f"q:{query.lower()}"
    if key in seen:
        return None
    seen.add(key)
    avg = (specific + recent + credible) / 3
    s = Source(company_id=company.id, category=category, kind=kind, name=name[:300], url=url, query=query,
               reason=reason, specific=round(specific, 2), recent=round(recent, 2), credible=round(credible, 2),
               competitor_id=competitor_id, discovered_by=discovered_by,
               status=status or ("approved" if avg >= 0.62 and specific >= 0.6 else "proposed"))
    db.add(s)
    return s


def _existing_keys(db, company) -> set:
    keys = set()
    for s in db.query(Source).filter(Source.company_id == company.id).all():
        keys.add(f"q:{s.query.lower()}" if s.kind == "news_query" else normalize_url(s.url))
    return keys


def competitor_sources(db: Session, company: Company, comps: list[Competitor], seen: set, progress) -> int:
    n = 0
    for c in comps:
        disamb = company.keywords[0] if company.keywords else company.industry
        nm = re.sub(r"\s*\(.*?\)", "", c.name).strip()
        q = f'"{nm}" {disamb}' if len(nm.split()) == 1 else f'"{nm}"'
        if _add_source(db, company, seen, category="competitors", kind="news_query", name=f"News coverage: {c.name}",
                       url=f"news://{q}", query=q, competitor_id=c.id,
                       reason=f"Tracks launches, pricing, partnerships, funding and expansion news about {c.name}. "
                              f"{c.why_relevant}",
                       specific=0.85, recent=0.9, credible=0.7):
            n += 1
        if not c.website:
            continue
        progress(f"Probing {c.name} website")
        home = probe(c.website)
        if not home["ok"]:
            continue
        if home["kind"] == "rss" and home["feed"]:
            _add_source(db, company, seen, category="competitors", kind="rss", name=f"{c.name} feed", url=home["feed"],
                        competitor_id=c.id, reason=f"{c.name}'s own published feed: first-party announcements.",
                        specific=0.9, recent=_recency_score(home["latest"], "rss"), credible=0.85)
            n += 1
        r = fetch(c.website)
        links = page_links(r.text, r.url) if r.ok else []
        # only top-level section pages (e.g. /blog, /newsroom, /pricing), never individual articles
        want = {"news": ("newsroom", "news", "press", "blog", "updates", "announcements", "media", "stories"),
                "pricing": ("pricing", "plans", "price", "fees"), "careers": ("careers", "jobs", "career")}
        picked = {}
        for href, _ in links:
            p_ = urlparse(href)
            segs = [s for s in p_.path.lower().split("/") if s]
            if domain(href) != domain(c.website) or len(segs) != 1 or p_.query:
                continue
            for label, names in want.items():
                if label not in picked and segs[0] in names:
                    picked[label] = href
        base = f"{urlparse(r.url if r.ok else c.website).scheme}://{urlparse(r.url if r.ok else c.website).netloc}"
        for label, names in want.items():  # common paths not linked from the homepage
            if label not in picked:
                for n_ in names[:3]:
                    t = fetch(f"{base}/{n_}")
                    if t.ok and urlparse(t.url).path.strip("/").lower() == n_:
                        picked[label] = t.url
                        break
        for label, href in picked.items():
            p = probe(href)
            if not p["ok"]:
                continue
            reasons = {
                "news": (f"{c.name}'s newsroom/blog: first-party product, partnership and positioning changes.", 0.9),
                "pricing": (f"{c.name}'s pricing page: monitored for price or package changes that affect "
                            f"{company.name}'s competitiveness.", 0.95),
                "careers": (f"{c.name}'s careers page: hiring patterns reveal expansion and new capabilities.", 0.7),
            }
            reason, spec = reasons[label]
            url = p["feed"] or p["url"]
            if _add_source(db, company, seen, category="competitors", kind="rss" if p["feed"] else "web",
                           name=f"{c.name} {label}", url=url, competitor_id=c.id, reason=reason, specific=spec,
                           recent=_recency_score(p["latest"], p["kind"]) if label == "news" else 0.6,
                           credible=0.85):
                n += 1
    db.commit()
    return n


def discover_category_sources(db: Session, company: Company, seen: set, progress, focus: str = "") -> dict:
    prof = profile_text(db, company)
    progress("Planning source search")
    plan = complete_json(
        f"""{prof}
{"CONTEXT CHANGE / FOCUS: " + focus if focus else ""}
Today's date: {datetime.utcnow():%Y-%m-%d}. Do NOT put years in queries (monitors run continuously).

Plan intelligence sources for this company. We cannot use Reddit, Quora, LinkedIn or Google News (their
robots.txt forbids crawlers) and we never bypass logins. For market sources, name the specific regulators,
government departments, industry bodies and trade publications that matter in this company's geographies
(e.g. "<regulator name> news releases", "<trade publication> <topic>").
Return JSON:
{{
 "customer_queries": ["5 web-search queries to find public places where THIS company's customers discuss the problems
    it solves: forums, communities, Q&A, review pages, complaint boards, student/user blogs. Use the customer's
    language, not the brand name."],
 "customer_news_themes": ["2 short news-search queries about customer problems/pain trends in this space"],
 "market_queries": ["6 web-search queries to find regulators, government policy pages, industry bodies, trade
    publications and research bodies that publish developments material to this business and its geographies"],
 "market_news_themes": ["4 short news-search queries for regulatory/industry/economic/technology developments that
    would materially affect this business (be specific, e.g. include country + policy area)"]
}}""",
        temperature=0.3,
        max_tokens=2000,
    )
    counts = {"customers": 0, "market": 0}
    for cat, key in (("customers", "customer_news_themes"), ("market", "market_news_themes")):
        for q in plan.get(key, [])[:4]:
            if _add_source(db, company, seen, category=cat, kind="news_query", name=f"News: {q}", url=f"news://{q}",
                           query=q, reason=f"News monitor for '{q}': catches {('customer pain trends' if cat == 'customers' else 'regulatory, industry and market developments')} "
                                         f"relevant to {company.name}'s market.",
                           specific=0.75, recent=0.9, credible=0.65, discovered_by="discovery"):
                counts[cat] += 1

    candidates = {}
    own = domain(company.website)
    for cat, key in (("customers", "customer_queries"), ("market", "market_queries")):
        for q in plan.get(key, [])[:6]:
            progress(f"Searching: {q}")
            for r in web_search(q, 8):
                u = r["url"]
                if domain(u) == own or any(s in u for s in SOCIAL) or u.lower().endswith(".pdf"):
                    continue
                candidates.setdefault(normalize_url(u), dict(r, category=cat, query=q))
    cand = [c for k, c in candidates.items() if k not in seen][:40]
    progress(f"Probing {len(cand)} candidate sources (robots.txt, liveness, feeds)")
    with ThreadPoolExecutor(max_workers=6) as ex:
        probes = list(ex.map(lambda c: probe(c["url"]), cand))
    usable = [(c, p) for c, p in zip(cand, probes) if p["ok"] and p["allowed"]]
    blocked = [c["url"] for c, p in zip(cand, probes) if not p["allowed"]]

    if usable:
        listing = "\n".join(
            f"{i}. [{c['category']}] {c['url']} | {c['title'][:90]} | {c['snippet'][:160]} | feed={'yes' if p['feed'] else 'no'} "
            f"| latest={p['latest'].date() if p['latest'] else 'unknown'}"
            for i, (c, p) in enumerate(usable))
        progress("Scoring candidate sources")
        judged = complete_json(
            f"""{prof}

Candidate sources found by web search (all reachable and allowed by robots.txt):
{listing}

Judge each candidate as a CONTINUOUS MONITORING source for {company.name}. Official regulator/government
news pages and specialist trade publications are valuable market sources even if not updated daily.
Keep only sources that are
Specific (about this company's actual problem space/market), Recent (updated regularly: news pages, forums,
listing pages, feeds - not one-off static articles), and Credible for the type of information.
A single old article is NOT a good monitoring source; its site's section/listing page might be.
Return JSON: {{"sources": [{{"i": index, "keep": true/false, "category": "customers|market",
"name": "short name", "reason": "why monitor this for {company.name} (1-2 sentences, specific)",
"specific": 0-1, "recent": 0-1, "credible": 0-1}}]}}""",
            max_tokens=5000,
        )
        for j in judged.get("sources", []):
            i = j.get("i")
            if not isinstance(i, int) or i >= len(usable) or not j.get("keep"):
                continue
            c, p = usable[i]
            rec = max(_recency_score(p["latest"], p["kind"]), float(j.get("recent", 0.5))) if p["latest"] is None \
                else _recency_score(p["latest"], p["kind"])
            cat = j.get("category") if j.get("category") in ("customers", "market") else c["category"]
            if _add_source(db, company, seen, category=cat, kind="rss" if p["feed"] else "web",
                           name=j.get("name") or p["title"] or domain(c["url"]), url=p["feed"] or p["url"],
                           reason=j.get("reason", ""), specific=float(j.get("specific", 0.5)), recent=rec,
                           credible=float(j.get("credible", 0.5))):
                counts[cat] += 1
    db.commit()
    return {**counts, "blocked_by_robots": blocked[:20]}


def ensure_internal_source(db: Session, company: Company):
    if not db.query(Source).filter(Source.company_id == company.id, Source.category == "internal").first():
        db.add(Source(company_id=company.id, category="internal", kind="upload", name="Internal uploads",
                      url="upload://", status="approved", specific=1.0, recent=1.0, credible=0.9,
                      reason="Founder-provided CRM exports, call/meeting transcripts, support logs and reports "
                             "(CSV, Excel, PDF, text). First-party evidence of objections, lost deals and requests.",
                      discovered_by="system"))
        db.commit()


def build_signal_stack(db: Session, company: Company, progress=lambda m: None) -> dict:
    seen = _existing_keys(db, company)
    progress("Discovering competitors")
    comps = discover_competitors(db, company, progress)
    approved = db.query(Competitor).filter(Competitor.company_id == company.id, Competitor.status == "approved").count()
    if approved < 5:
        progress("Fewer than 5 competitors found - widening the search")
        comps += discover_competitors(db, company, progress, extra_round=True)
    comps = list({c.id: c for c in comps}.values())
    n_comp = competitor_sources(db, company, comps, seen, progress)
    cat = discover_category_sources(db, company, seen, progress)
    ensure_internal_source(db, company)
    if company.stage in ("created", "researched", "interviewed"):
        company.stage = "stack_ready"
    db.commit()
    return {"competitors": len(comps), "competitor_sources": n_comp, "customer_sources": cat["customers"],
            "market_sources": cat["market"], "blocked_by_robots": cat["blocked_by_robots"]}
