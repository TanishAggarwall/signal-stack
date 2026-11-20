"""Step 8: Monday Morning Brief. Category sections are rendered straight from stored signals; the LLM only
synthesises (summary / opportunities / risks / actions / watch-list) and every item must cite signal ids that
exist. Empty categories say so; nothing is invented to fill space."""
from datetime import timedelta

import markdown as md
from sqlalchemy.orm import Session

from ..llm import LLMError, complete_json
from ..models import Brief, BriefAction, Company, Document, Signal, Source, now
from .research import profile_text

SECTIONS = [("customers", "Customer Signals"), ("competitors", "Competitor Intelligence"),
            ("market", "Market Intelligence"), ("internal", "Internal Business Intelligence")]


def _period(db: Session, company: Company):
    last = db.query(Brief).filter(Brief.company_id == company.id).order_by(Brief.id.desc()).first()
    end = now()
    start = last.period_end if last else end - timedelta(days=company.settings.get("lookback_days", 30))
    return start, end


def _card(s: Signal, n: int, doc: Document) -> dict:
    return {"ref": n, "signal_id": s.id, "title": s.title, "what_happened": s.what_happened,
            "why_it_matters": s.why_it_matters, "consider_doing": s.consider_doing, "type": s.signal_type,
            "impact": s.impact, "urgency": s.urgency, "score": s.score, "competitor": s.competitor_name,
            "business_area": s.business_area, "verification": s.verification, "url": doc.url if doc else "",
            "rank_explanation": s.rank_explanation}


def generate_brief(db: Session, company: Company, trigger: str = "manual", job_id=None, progress=lambda m: None) -> Brief:
    start, end = _period(db, company)
    sigs = db.query(Signal).filter(Signal.company_id == company.id, Signal.dismissed.is_(False),
                                   Signal.created_at >= start, Signal.created_at <= end) \
        .order_by(Signal.score.desc()).all()
    docs = {d.id: d for d in db.query(Document).filter(Document.id.in_([s.document_id for s in sigs] or [0]))}
    srcs = {s.id: s for s in db.query(Source).filter(Source.company_id == company.id)}
    refs = {s.id: i + 1 for i, s in enumerate(sigs)}  # appendix numbering

    content = {"company": company.name, "website": company.website, "period_start": start.isoformat(),
               "period_end": end.isoformat(), "generated_at": now().isoformat(), "limitations": []}
    by_cat = {c: [s for s in sigs if s.category == c] for c, _ in SECTIONS}
    for cat, _ in SECTIONS:
        content[cat] = [_card(s, refs[s.id], docs.get(s.document_id)) for s in by_cat[cat][:8]]

    top = sigs[:25]
    if top:
        progress("Writing executive synthesis")
        listing = "\n".join(
            f"[id={s.id}] ({s.category}, {s.signal_type}, score {s.score}, impact {s.impact}, urgency {s.urgency}, "
            f"{s.verification}) {s.title} :: {s.what_happened} :: Why: {s.why_it_matters} :: Consider: {s.consider_doing}"
            for s in top)
        try:
            data = complete_json(
                f"""{profile_text(db, company, 4000)}

These are this period's ranked, evidence-backed signals for {company.name} (only these exist; do not add others):
{listing}

Write the decision-relevant parts of the Monday Morning Brief for the founder/CEO. Every item MUST cite the
signal ids it is based on. No generic advice: each item must name the specific product, segment, competitor,
geography or priority it concerns. If the evidence does not support an item, leave it out.
Return JSON:
{{
 "executive_summary": [{{"headline": "...", "so_what": "1 sentence business implication", "signal_ids": [..]}}] (max 5, most important first),
 "opportunities": [{{"title": "...", "evidence": "what in the signals supports it", "impact": "...", "next_step": "...",
                    "priority": "high|medium|low", "signal_ids": [..]}}] (aim for 3-5, only if supported),
 "risks": [{{"title": "...", "possible_impact": "...", "urgency": "high|medium|low", "signal_ids": [..]}}],
 "actions": [{{"action": "...", "reason": "...", "owner": "role e.g. Founder, Marketing lead, Partnerships, Product",
              "priority": "high|medium|low", "signal_ids": [..]}}] (3-7, prioritised for this week),
 "watch": [{{"item": "early development to keep monitoring", "why": "...", "signal_ids": [..]}}]
}}""",
                max_tokens=5000, temperature=0.3)
        except LLMError as e:
            data = {}
            content["limitations"].append(f"AI synthesis unavailable this run ({e}); signal sections are still complete.")
        valid = {s.id for s in top}

        def clean(items, n=None):
            out = []
            for it in items or []:
                ids = [i for i in it.get("signal_ids", []) if isinstance(i, int) and i in valid]
                if ids:
                    it["signal_ids"] = ids
                    it["refs"] = [refs[i] for i in ids]
                    out.append(it)
            return out[:n] if n else out

        content["executive_summary"] = clean(data.get("executive_summary"), 5)
        content["opportunities"] = clean(data.get("opportunities"))
        content["risks"] = clean(data.get("risks"))
        content["actions"] = clean(data.get("actions"), 7)
        content["watch"] = clean(data.get("watch"))
    else:
        for k in ("executive_summary", "opportunities", "risks", "actions", "watch"):
            content[k] = []
        content["limitations"].append("No new evidence-backed developments were collected in this period.")
    if len(content["opportunities"]) < 3:
        content["limitations"].append(
            f"Only {len(content['opportunities'])} opportunit{'y' if len(content['opportunities']) == 1 else 'ies'} "
            "could be supported by collected evidence this period; we do not invent more.")

    appendix = []
    for s in sigs:
        d = docs.get(s.document_id)
        src = srcs.get(d.source_id) if d else None
        appendix.append({"ref": refs[s.id], "signal_id": s.id, "title": s.title, "source": src.name if src else "",
                         "publisher": d.publisher if d else "", "url": d.url if d else "",
                         "published": d.published_at.date().isoformat() if d and d.published_at else "unknown",
                         "discovered": d.fetched_at.date().isoformat() if d else "",
                         "snippet": s.evidence_quote, "verification": s.verification,
                         "source_reliability": s.source_reliability, "evidence_strength": s.evidence_strength,
                         "full_text_accessed": bool(d and d.full_text)})
    content["appendix"] = appendix
    content["stats"] = {"signals": len(sigs), **{c: len(by_cat[c]) for c, _ in SECTIONS},
                        "sources_monitored": sum(1 for s in srcs.values() if s.status == "approved")}

    brief = Brief(company_id=company.id, period_start=start, period_end=end, content=content, trigger=trigger, job_id=job_id)
    db.add(brief)
    db.flush()
    for a in content["actions"]:
        db.add(BriefAction(brief_id=brief.id, action=a.get("action", ""), reason=a.get("reason", ""),
                           owner=a.get("owner", ""), priority=a.get("priority", "medium"), signal_ids=a["signal_ids"]))
    brief.markdown = to_markdown(content)
    db.commit()
    return brief


def _refs(it):
    return " " + "".join(f"[{r}]" for r in it.get("refs", [])) if it.get("refs") else ""


def to_markdown(c: dict) -> str:
    L = [f"# Monday Morning Brief — {c['company']}",
         f"_Period {c['period_start'][:10]} → {c['period_end'][:10]} · generated {c['generated_at'][:16].replace('T', ' ')} UTC · "
         f"{c['stats']['signals']} evidence-backed signals from {c['stats']['sources_monitored']} monitored sources_", ""]
    L += ["## 1. Executive Summary"]
    L += [f"{i}. **{x['headline']}** — {x.get('so_what', '')}{_refs(x)}" for i, x in enumerate(c["executive_summary"], 1)] \
        or ["No significant developments this period."]
    for n, (cat, title) in enumerate(SECTIONS, 2):
        L += ["", f"## {n}. {title}"]
        if not c[cat]:
            L.append(f"_No meaningful {title.lower()} development was detected in this period._")
        for s in c[cat]:
            tag = {"opportunity": "🟢 Opportunity", "threat": "🔴 Threat"}.get(s["type"], "⚪ Neutral")
            L += [f"**{s['title']}** [{s['ref']}] — {tag} · impact {s['impact']}/5 · urgency {s['urgency']}/5 · {s['verification']}",
                  f"- *What happened (evidence):* {s['what_happened']}",
                  f"- *Why it matters (analysis):* {s['why_it_matters']}",
                  f"- *Consider:* {s['consider_doing']}", ""]
    L += ["", "## 6. Opportunities Identified"]
    L += [f"- **{o['title']}** ({o.get('priority', '')} priority){_refs(o)}\n  - Evidence: {o.get('evidence', '')}\n"
          f"  - Impact: {o.get('impact', '')}\n  - Next step: {o.get('next_step', '')}" for o in c["opportunities"]] \
        or ["_No evidence-backed opportunities this period._"]
    L += ["", "## 7. Risks & Threats"]
    L += [f"- **{r['title']}** (urgency: {r.get('urgency', '')}){_refs(r)} — {r.get('possible_impact', '')}" for r in c["risks"]] \
        or ["_No significant risks detected this period._"]
    L += ["", "## 8. Recommended Actions for This Week", "| # | Action | Owner | Priority | Reason |", "|---|---|---|---|---|"]
    L += [f"| {i} | {a['action']} | {a.get('owner', '')} | {a.get('priority', '')} | {a.get('reason', '')}{_refs(a)} |"
          for i, a in enumerate(c["actions"], 1)] or ["| – | No actions recommended | | | |"]
    L += ["", "## 9. What We Should Watch"]
    L += [f"- **{w['item']}** — {w.get('why', '')}{_refs(w)}" for w in c["watch"]] or ["_Nothing flagged._"]
    if c.get("limitations"):
        L += ["", "### Limitations"] + [f"- {x}" for x in c["limitations"]]
    L += ["", "## 10. Source Appendix", "| Ref | Development | Source | Published | Discovered | Evidence snippet | Verification |",
          "|---|---|---|---|---|---|---|"]
    for a in c["appendix"]:
        link = f"[{a['publisher'] or a['source']}]({a['url']})" if a["url"].startswith("http") else a["publisher"] or a["source"]
        L.append(f"| [{a['ref']}] | {a['title']} | {link} | {a['published']} | {a['discovered']} | “{a['snippet'][:220]}” | "
                 f"{a['verification']}; reliability {a['source_reliability']}; evidence {a['evidence_strength']}"
                 f"{'' if a['full_text_accessed'] else '; headline/snippet only'} |")
    L += ["", "_Facts are quoted from the linked sources; 'why it matters' and recommendations are AI analysis. "
          "Confidence scores are not proof that an event is true._"]
    return "\n".join(L)


def to_email_html(markdown_text: str) -> str:
    body = md.markdown(markdown_text, extensions=["tables"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Monday Brief</title></head>
<body style="font-family:Inter,Segoe UI,Arial,sans-serif;max-width:760px;margin:24px auto;color:#1f1d2b;line-height:1.55">
<style>table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid #e4e2f0;padding:6px;vertical-align:top}}
th{{background:#f3f0ff}}h1{{color:#5b3df5}}h2{{border-bottom:2px solid #ede9fe;padding-bottom:4px;margin-top:28px}}a{{color:#5b3df5}}</style>
{body}</body></html>"""
