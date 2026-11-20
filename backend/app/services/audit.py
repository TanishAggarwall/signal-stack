"""Monthly Signal Stack audit + business-context change reassessment."""
from datetime import timedelta

from sqlalchemy.orm import Session

from ..fetch import fetch, normalize_url
from ..llm import complete_json
from ..models import Company, ContextChange, ProfileFact, Source, SourceCheck, now
from .discovery import _existing_keys, discover_category_sources
from .research import profile_text


def run_audit(db: Session, company: Company, progress=lambda m: None) -> dict:
    sources = db.query(Source).filter(Source.company_id == company.id, Source.status != "removed",
                                      Source.kind != "upload").all()
    report = {"checked": len(sources), "dead": [], "blocked": [], "duplicates": [], "inactive": [],
              "declining_relevance": [], "new_candidates": [], "recommend_remove": [], "recommend_add": []}
    cutoff = now() - timedelta(days=45)

    # 1. dead URLs (re-check now, independent of the weekly crawl)
    for i, s in enumerate(sources, 1):
        if s.kind == "news_query":
            continue
        progress(f"Checking URL {i}/{len(sources)}")
        r = fetch(s.url)
        if r.blocked:
            s.health = "blocked"
            report["blocked"].append({"id": s.id, "name": s.name, "url": s.url, "detail": r.error})
        elif not r.ok:
            s.health = "dead"
            report["dead"].append({"id": s.id, "name": s.name, "url": s.url, "detail": r.error or f"HTTP {r.status}"})
    # 2. duplicates (same normalised URL / same query)
    seen = {}
    for s in sources:
        key = f"q:{s.query.lower()}" if s.kind == "news_query" else normalize_url(s.url)
        if key in seen:
            s.duplicate_of = seen[key].id
            report["duplicates"].append({"id": s.id, "name": s.name, "duplicate_of": seen[key].name})
        else:
            seen[key] = s
    # 3. inactive + declining relevance (from crawl history)
    for s in sources:
        checks = db.query(SourceCheck).filter(SourceCheck.source_id == s.id).order_by(SourceCheck.id.desc()).limit(8).all()
        if len(checks) >= 2 and not any(c.new_items for c in checks) and (not s.last_new_item or s.last_new_item < cutoff):
            s.health = "stale" if s.health == "ok" else s.health
            report["inactive"].append({"id": s.id, "name": s.name, "checks": len(checks)})
        if s.total_items >= 8 and s.total_signals / max(s.total_items, 1) < 0.05:
            report["declining_relevance"].append({"id": s.id, "name": s.name, "items": s.total_items,
                                                  "signals": s.total_signals})
    removable = {d["id"] for k in ("dead", "duplicates") for d in report[k]} | \
                {d["id"] for d in report["inactive"] if d["checks"] >= 4} | {d["id"] for d in report["declining_relevance"]}
    report["recommend_remove"] = [{"id": s.id, "name": s.name, "url": s.url} for s in sources if s.id in removable]
    db.commit()

    # 4. newly discovered sources (added as 'proposed' for the founder to approve)
    progress("Looking for new sources")
    before = {s.id for s in db.query(Source).filter(Source.company_id == company.id)}
    discover_category_sources(db, company, _existing_keys(db, company), progress)
    new = db.query(Source).filter(Source.company_id == company.id, ~Source.id.in_(before)).all()
    for s in new:
        s.status = "proposed"
        s.discovered_by = "monthly_audit"
    db.commit()
    report["new_candidates"] = [{"id": s.id, "name": s.name, "category": s.category, "reason": s.reason} for s in new]
    report["recommend_add"] = report["new_candidates"]
    report["health_summary"] = {h: sum(1 for s in sources if s.health == h)
                                for h in ("ok", "dead", "blocked", "stale", "error", "unchecked")}
    return report


def reassess_context(db: Session, company: Company, change_text: str, progress=lambda m: None) -> dict:
    """Founder changed the business context: update profile, re-score every source, propose new ones."""
    old_profile = profile_text(db, company)
    db.add(ProfileFact(company_id=company.id, field="context_change", value=change_text, status="founder",
                       evidence="Business context update"))
    company.context_version += 1
    db.commit()
    new_profile = profile_text(db, company)
    sources = db.query(Source).filter(Source.company_id == company.id, Source.status == "approved",
                                      Source.category != "internal").all()
    listing = "\n".join(f"[{s.id}] ({s.category}) {s.name} | {s.query or s.url} | reason: {s.reason[:150]}" for s in sources)
    progress("Re-scoring sources against the new context")
    data = complete_json(
        f"""The founder changed the business context.
CHANGE: {change_text}

OLD PROFILE:
{old_profile}

CURRENT SOURCES:
{listing}

For every source decide if it is still useful under the new context.
Return JSON: {{"summary": "what changed strategically (2-3 sentences)",
"sources": [{{"id": n, "decision": "keep|remove|lower_priority", "specific": 0-1, "why": "..."}}],
"new_focus": "1-2 sentences describing what new sources should cover",
"new_keywords": ["..."]}}""",
        max_tokens=5000)
    by_id = {s.id: s for s in sources}
    removed, lowered = [], []
    for d in data.get("sources", []):
        s = by_id.get(d.get("id"))
        if not s:
            continue
        if isinstance(d.get("specific"), (int, float)):
            s.specific = round(float(d["specific"]), 2)
        if d.get("decision") == "remove":
            s.status, s.removed_reason = "proposed", f"Context change v{company.context_version}: {d.get('why', '')}"
            removed.append({"id": s.id, "name": s.name, "why": d.get("why", "")})
        elif d.get("decision") == "lower_priority":
            lowered.append({"id": s.id, "name": s.name, "why": d.get("why", "")})
    if data.get("new_keywords"):
        company.keywords = list(dict.fromkeys((company.keywords or []) + data["new_keywords"]))[:25]
    db.commit()
    before = {s.id for s in db.query(Source).filter(Source.company_id == company.id)}
    discover_category_sources(db, company, _existing_keys(db, company), progress, focus=data.get("new_focus", change_text))
    new = db.query(Source).filter(Source.company_id == company.id, ~Source.id.in_(before)).all()
    for s in new:
        s.status, s.discovered_by = "proposed", "context_change"
    result = {"summary": data.get("summary", ""), "no_longer_useful": removed, "lower_priority": lowered,
              "new_sources": [{"id": s.id, "name": s.name, "category": s.category, "reason": s.reason} for s in new],
              "new_keywords": data.get("new_keywords", []), "old_profile": old_profile, "new_profile": new_profile}
    db.add(ContextChange(company_id=company.id, change_text=change_text, result=result))
    db.commit()
    return result
