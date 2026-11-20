"""Step 3: adaptive founder interview. 10 core questions, written by the LLM per company from the research
profile + earlier answers. One at a time, follow-ups when useful, skippable, editable later."""
from sqlalchemy.orm import Session

from ..fetch import jaccard, shingles
from ..llm import complete_json
from ..models import Company, InterviewTurn, ProfileFact, now
from .research import profile_text

CORE_QUESTIONS = 10
MAX_FOLLOWUPS = 4
TOPICS = {
    "revenue_lines": "Primary business lines and revenue streams",
    "best_customers": "Highest-value customer segments",
    "customer_problems": "Current customer problems and unmet needs",
    "why_us": "Why customers choose the company over alternatives",
    "competitors": "Important competitors or substitutes",
    "market_changes": "Major industry and market changes",
    "material_risks": "Developments that could materially affect the business",
    "growth_priorities": "Growth priorities over the next 6-12 months",
    "internal_data": "Internal business information that should influence decisions (CRM, sales calls, support)",
    "decisions": "Decisions the intelligence system should help the founder make",
}


def _turns(db: Session, company_id: int) -> list[InterviewTurn]:
    return db.query(InterviewTurn).filter(InterviewTurn.company_id == company_id).order_by(InterviewTurn.seq).all()


def transcript(turns: list[InterviewTurn]) -> str:
    out = []
    for t in turns:
        a = "(skipped - confidential)" if t.skipped else (t.answer or "(not answered yet)")
        out.append(f"Q{t.seq} [{t.topic}{' follow-up' if t.is_followup else ''}]: {t.question}\nA: {a}")
    return "\n".join(out)


def state(db: Session, company: Company) -> dict:
    turns = _turns(db, company.id)
    core_done = sum(1 for t in turns if not t.is_followup and (t.answer is not None or t.skipped))
    pending = next((t for t in turns if t.answer is None and not t.skipped), None)
    return {"turns": turns, "core_done": core_done, "pending": pending,
            "complete": core_done >= CORE_QUESTIONS and pending is None}


def next_question(db: Session, company: Company) -> InterviewTurn | None:
    st = state(db, company)
    if st["pending"]:
        return st["pending"]
    if st["complete"]:
        return None
    turns = st["turns"]
    covered = {t.topic for t in turns if not t.is_followup}
    remaining = {k: v for k, v in TOPICS.items() if k not in covered}
    if not remaining:  # all topics covered but < 10 core (shouldn't happen) -> allow any topic
        remaining = TOPICS
    asked = [t.question for t in turns]

    for attempt in range(2):
        data = complete_json(
            f"""You are interviewing the founder of this company to configure a business-intelligence system.

COMPANY RESEARCH PROFILE (verified = from their website, assumption = our inference, founder = told by founder):
{profile_text(db, company)}

INTERVIEW SO FAR:
{transcript(turns) or "(none yet)"}

Topics still to cover (key: description):
{chr(10).join(f"- {k}: {v}" for k, v in remaining.items())}

Write question {st['core_done'] + 1} of {CORE_QUESTIONS}. Pick the most useful remaining topic.
The question MUST be specific to this company: reference its actual products, segments, market or something
from the research (e.g. confirm or challenge an assumption). Never ask something already answered. Keep it to
1-2 sentences a busy founder can answer quickly. Make clear they may skip if confidential is NOT needed (UI handles it).
{"Previous draft was too similar to an earlier question; ask something different." if attempt else ""}
Return JSON: {{"topic": "<topic key>", "question": "...", "rationale": "why this matters for monitoring (1 sentence)"}}""",
            temperature=0.5,
            max_tokens=1200,
        )
        q = (data.get("question") or "").strip()
        if q and max((jaccard(shingles(q, 3), shingles(a, 3)) for a in asked), default=0) < 0.5:
            break
    topic = data.get("topic") if data.get("topic") in TOPICS else next(iter(remaining))
    turn = InterviewTurn(company_id=company.id, seq=len(turns) + 1, topic=topic, question=q,
                         rationale=data.get("rationale", ""))
    db.add(turn)
    db.commit()
    return turn


def _apply_answer(db: Session, company: Company, turn: InterviewTurn, allow_followup: bool) -> dict:
    """Extract structured facts from an answer into the profile; optionally propose a follow-up."""
    db.query(ProfileFact).filter(ProfileFact.company_id == company.id,
                                 ProfileFact.source_url == f"interview:{turn.id}").delete()
    if turn.skipped or not (turn.answer or "").strip():
        db.commit()
        return {}
    turns = _turns(db, company.id)
    followups_used = sum(1 for t in turns if t.is_followup)
    can_follow = allow_followup and not turn.is_followup and followups_used < MAX_FOLLOWUPS
    data = complete_json(
        f"""Company: {company.name}. Interview question ({turn.topic}): {turn.question}
Founder's answer: \"\"\"{turn.answer}\"\"\"

1. Extract the concrete facts from the answer for the company profile. Use only what the founder said.
   fields: revenue_lines, customer_segments, customer_problems, differentiators, competitors, market_changes,
   material_risks, growth_priorities, internal_data, decisions_to_support, geography, other.
   Name each competitor/substitute the founder mentions as its own fact with field "competitors".
2. {"Decide if ONE short follow-up question is clearly worth asking (answer was vague, or opened an important thread for monitoring such as a named competitor, a new market, or a risk). Usually not needed." if can_follow else "No follow-up allowed."}
Return JSON: {{"facts": [{{"field": "...", "value": "..."}}], "followup": "question text or empty string",
"followup_reason": "..."}}""",
        max_tokens=1500,
    )
    for f in data.get("facts", [])[:12]:
        v = (f.get("value") or "").strip()
        if v:
            db.add(ProfileFact(company_id=company.id, field=(f.get("field") or "other")[:80], value=v,
                               status="founder", source_url=f"interview:{turn.id}",
                               evidence=f"Founder interview Q{turn.seq}"))
    fu = (data.get("followup") or "").strip() if can_follow else ""
    if fu:
        db.add(InterviewTurn(company_id=company.id, seq=len(turns) + 1, topic=turn.topic, question=fu,
                             rationale=data.get("followup_reason", ""), is_followup=True, parent_id=turn.id))
    db.commit()
    return {"facts_added": len(data.get("facts", [])), "followup": bool(fu)}


def answer(db: Session, company: Company, turn: InterviewTurn, text: str | None, skip: bool) -> dict:
    turn.skipped = bool(skip)
    turn.answer = None if skip else (text or "").strip()
    turn.answered_at = now()
    db.commit()
    result = _apply_answer(db, company, turn, allow_followup=True)
    st = state(db, company)
    if st["complete"] and company.stage in ("created", "researched"):
        company.stage = "interviewed"
        db.commit()
    return result


def edit_answer(db: Session, company: Company, turn: InterviewTurn, text: str | None, skip: bool) -> dict:
    turn.skipped = bool(skip)
    turn.answer = None if skip else (text or "").strip()
    turn.answered_at = now()
    db.commit()
    return _apply_answer(db, company, turn, allow_followup=False)
