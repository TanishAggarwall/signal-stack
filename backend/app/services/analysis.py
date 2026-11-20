"""Step 6: intelligence analysis. The LLM reads documents WE collected and must quote them verbatim; any
signal whose quote is not found in the stored text is rejected. Facts and interpretation are stored apart."""
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..fetch import domain, quote_in_text
from ..llm import LLMError, complete_json
from ..models import Company, Competitor, Document, ProfileFact, Signal, Source
from .research import profile_text

log = logging.getLogger("analysis")
BATCH = 4
TEXT_LIMIT = 2600
STALE_DAYS = 60


def _terms(db: Session, company: Company) -> tuple[set[str], list[str]]:
    comps = [c.name for c in db.query(Competitor).filter(Competitor.company_id == company.id,
                                                         Competitor.status == "approved")]
    words = set()
    for k in (company.keywords or []) + [company.industry, company.name]:
        words |= {w for w in re.findall(r"[a-z]{4,}", (k or "").lower())}
    words -= {"with", "from", "that", "this", "their", "services", "company", "platform", "online"}
    return words, comps


def _prefilter(doc: Document, words: set[str], comps: list[str], company: Company) -> bool:
    """Cheap relevance gate before spending LLM quota."""
    t = f"{doc.title} {doc.text[:5000]}".lower()
    if company.name.lower() in t or any(c.lower() in t for c in comps):
        return True
    hits = sum(1 for w in words if w in t)
    return hits >= 2


def _priorities(db: Session, company: Company) -> str:
    rows = db.query(ProfileFact).filter(ProfileFact.company_id == company.id, ProfileFact.field.in_(
        ["growth_priorities", "decisions_to_support", "material_risks", "customer_problems"])).all()
    return "\n".join(f"- {r.field}: {r.value}" for r in rows)[:2500]


def analyze_documents(db: Session, company: Company, progress=lambda m: None) -> dict:
    words, comps = _terms(db, company)
    comp_ids = {c.name.lower(): c.id for c in db.query(Competitor).filter(Competitor.company_id == company.id)}
    docs = db.query(Document).filter(Document.company_id == company.id, Document.analyzed.is_(False),
                                     Document.duplicate_of.is_(None)).order_by(Document.id).all()
    sources = {s.id: s for s in db.query(Source).filter(Source.company_id == company.id)}
    stats = {"documents": len(docs), "prefiltered_out": 0, "signals": 0, "rejected_unverified_quote": 0,
             "not_relevant": 0, "llm_errors": 0}
    todo = []
    for d in docs:
        if d.source_id and sources.get(d.source_id) and sources[d.source_id].kind == "upload":
            continue  # internal files are analysed by services.internal
        if _prefilter(d, words, comps, company):
            todo.append(d)
        else:
            d.analyzed, d.relevant = True, False
            stats["prefiltered_out"] += 1
    db.commit()

    prof = profile_text(db, company, 4500)
    prios = _priorities(db, company)
    for b in range(0, len(todo), BATCH):
        batch = todo[b:b + BATCH]
        progress(f"Analysing documents {b + 1}-{b + len(batch)} of {len(todo)}")
        blocks = []
        for i, d in enumerate(batch):
            s = sources.get(d.source_id)
            blocks.append(f"### DOC {i}\nsource_category: {s.category if s else 'unknown'}\n"
                          f"source: {s.name if s else ''}\nurl: {d.url}\npublisher: {d.publisher}\n"
                          f"published: {d.published_at.date() if d.published_at else 'unknown'}\n"
                          f"title: {d.title}\ntext:\n{d.text[:TEXT_LIMIT]}")
        try:
            data = complete_json(
                f"""COMPANY PROFILE
{prof}

FOUNDER PRIORITIES / DECISIONS
{prios or "(not provided)"}

Known competitors: {", ".join(comps) or "none"}

Analyse each document below for {company.name}'s leadership. A document is a SIGNAL only if it reports a concrete
development (something happened or changed: launch, price change, policy, regulation, funding, partnership,
customer complaint pattern, market shift, data release) that plausibly matters to THIS business. General
evergreen advice, SEO listicles, ads and irrelevant news are NOT signals.
Today is {datetime.utcnow():%Y-%m-%d}. A development that happened more than {STALE_DAYS} days ago is old news and NOT a
signal, even if the page was published recently (e.g. an article recapping a 2024 launch). Give event_date whenever
the text states or clearly implies when it happened.

For each signal:
- FACTS (from the document only): title, what_happened (1-2 sentences, no opinion), event_date (YYYY-MM-DD or ""),
  evidence_quote: copy 12-40 consecutive words EXACTLY as they appear in the text (no paraphrase).
- INTERPRETATION (your analysis, clearly specific to {company.name}): why_it_matters (2 sentences that name the
  affected product/segment/priority - no generic advice), business_area, signal_type opportunity|threat|neutral,
  impact 1-5, urgency 1-5, relevance 0-1, consider_doing (one concrete, specific next step), competitor (name of the
  competitor involved, if any, else "").
- category: customers|competitors|market (use the source_category unless clearly wrong).

Return JSON: {{"results": [{{"doc": index, "is_signal": true/false, "reason_if_not": "...", ...signal fields}}]}}

{chr(10).join(blocks)}""",
                max_tokens=5000,
                prefer="gemini",
            )
        except LLMError as e:
            log.warning("analysis batch failed: %s", e)
            stats["llm_errors"] += 1
            continue  # documents stay unanalysed and are retried next run
        handled = set()
        for r in data.get("results", []):
            i = r.get("doc")
            if not isinstance(i, int) or i >= len(batch):
                continue
            d = batch[i]
            handled.add(i)
            d.analyzed = True
            if not r.get("is_signal"):
                d.relevant = False
                stats["not_relevant"] += 1
                continue
            quote = (r.get("evidence_quote") or "").strip()
            haystack = f"{d.title}\n{d.text}"
            if not quote_in_text(quote, haystack):
                d.relevant = None
                stats["rejected_unverified_quote"] += 1
                continue
            d.relevant = True
            s = sources.get(d.source_id)
            ev = None
            if r.get("event_date"):
                try:
                    ev = datetime.fromisoformat(r["event_date"][:10])
                except ValueError:
                    pass
            if ev and ev < datetime.utcnow() - timedelta(days=STALE_DAYS):
                stats["old_news"] = stats.get("old_news", 0) + 1
                d.relevant = False
                continue  # real, but not a new development
            comp = (r.get("competitor") or "").strip()
            cat = r.get("category") if r.get("category") in ("customers", "competitors", "market") else (s.category if s else "market")
            db.add(Signal(
                company_id=company.id, document_id=d.id, category=cat,
                competitor_id=comp_ids.get(comp.lower()) or (s.competitor_id if s else None), competitor_name=comp[:200],
                title=(r.get("title") or d.title)[:500], what_happened=r.get("what_happened", ""),
                event_date=ev or d.published_at, evidence_quote=quote, quote_verified=True,
                why_it_matters=r.get("why_it_matters", ""), business_area=(r.get("business_area") or "")[:120],
                signal_type=r.get("signal_type") if r.get("signal_type") in ("opportunity", "threat", "neutral") else "neutral",
                consider_doing=r.get("consider_doing", ""),
                impact=max(1, min(5, int(r.get("impact") or 2))), urgency=max(1, min(5, int(r.get("urgency") or 2))),
                relevance=max(0.0, min(1.0, float(r.get("relevance") or 0.5))),
            ))
            if s:
                s.total_signals += 1
            stats["signals"] += 1
        db.commit()
    return stats
