"""Step 7: signal ranking. Source reliability, evidence strength and strategic relevance are separate
measures; the LLM's own judgement is only one input and never counts as proof."""
import math
from datetime import timedelta

from sqlalchemy.orm import Session

from ..fetch import domain, jaccard, shingles
from ..models import Company, Document, Signal, Source, now

WEIGHTS = {"relevance": 0.25, "impact": 0.20, "urgency": 0.12, "reliability": 0.15,
           "evidence": 0.10, "recency": 0.10, "novelty": 0.08}

HIGH_TRUST = (".gov", ".gov.", ".gc.ca", ".gov.uk", ".edu", ".ac.", "europa.eu", "who.int", "un.org",
              "reuters.com", "bloomberg.com", "ft.com", "economictimes", "thehindu", "livemint", "business-standard",
              "timesofindia", "hindustantimes", "bbc.", "theguardian", "nytimes", "wsj.com", "techcrunch",
              "moneycontrol", "icef", "thepienews", "universityworldnews", "timeshighereducation", "indianexpress", "ndtv")


def source_reliability(doc: Document, src: Source | None) -> float:
    d = domain(doc.url)
    base = src.credible if src else 0.5
    if any(t in d for t in HIGH_TRUST):
        base = max(base, 0.85)
    if src and src.kind in ("rss", "web") and src.competitor_id:
        base = max(base, 0.8)  # first-party competitor announcement: reliable about itself
    if src and src.kind == "upload":
        base = 0.9
    if not doc.full_text:
        base -= 0.1  # only a headline/snippet was accessible
    return round(max(0.1, min(1.0, base)), 2)


def rank_signals(db: Session, company: Company) -> int:
    sigs = db.query(Signal).filter(Signal.company_id == company.id).all()
    if not sigs:
        return 0
    docs = {d.id: d for d in db.query(Document).filter(Document.company_id == company.id)}
    srcs = {s.id: s for s in db.query(Source).filter(Source.company_id == company.id)}
    # corroboration: near-duplicates from *other* domains, plus other signals on the same story
    dup_children: dict[int, list[Document]] = {}
    for d in docs.values():
        if d.duplicate_of:
            dup_children.setdefault(d.duplicate_of, []).append(d)
    sh = {s.id: shingles(f"{s.title} {s.what_happened}", 3) for s in sigs}

    for s in sigs:
        doc = docs.get(s.document_id)
        if not doc:
            continue
        src = srcs.get(doc.source_id)
        corr = {c.id for c in dup_children.get(doc.id, []) if domain(c.url) != domain(doc.url)}
        for o in sigs:
            od = docs.get(o.document_id)
            if o.id != s.id and od and domain(od.url) != domain(doc.url) and jaccard(sh[s.id], sh[o.id]) >= 0.3:
                corr.add(od.id)
        s.corroborating_doc_ids = sorted(corr)
        if s.category == "internal":
            s.verification = "internal"
        else:
            s.verification = "corroborated" if corr else "single-source"

        s.source_reliability = source_reliability(doc, src)
        s.evidence_strength = round(min(1.0, (0.45 if s.quote_verified else 0.1) + (0.15 if doc.full_text else 0)
                                        + 0.2 * min(len(corr), 2)), 2)
        ref = s.event_date or doc.published_at or doc.fetched_at
        age = max((now() - ref).days, 0) if ref else 30
        s.recency = round(math.exp(-age / 21), 2)
        earlier = [o for o in sigs if o.created_at < s.created_at - timedelta(days=5)]
        s.novelty = round(1 - max((jaccard(sh[s.id], sh[o.id]) for o in earlier), default=0), 2)

        parts = {
            "relevance": s.relevance, "impact": (s.impact - 1) / 4, "urgency": (s.urgency - 1) / 4,
            "reliability": s.source_reliability, "evidence": s.evidence_strength,
            "recency": s.recency, "novelty": s.novelty,
        }
        s.score = round(100 * sum(WEIGHTS[k] * v for k, v in parts.items()), 1)
        top = sorted(parts.items(), key=lambda kv: WEIGHTS[kv[0]] * kv[1], reverse=True)[:3]
        label = {"relevance": "highly relevant to stated priorities", "impact": f"impact {s.impact}/5",
                 "urgency": f"urgency {s.urgency}/5", "reliability": "reliable source",
                 "evidence": "strong evidence", "recency": "very recent", "novelty": "new development"}
        weak = [k for k, v in parts.items() if v < 0.4 and k in ("reliability", "evidence", "recency")]
        s.rank_explanation = (
            f"Score {s.score}: driven by " + ", ".join(label[k] for k, _ in top)
            + (f". Caution: low {', '.join(weak)}" if weak else "")
            + f". Verification: {s.verification}"
            + (f" ({len(corr)} other source(s))." if corr else ".")
        )
    db.commit()
    return len(sigs)
