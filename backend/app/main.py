"""FastAPI app: REST API for the dashboard + scheduler + external-cron endpoints."""
import logging
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from . import llm, scheduler
from .config import CRON_TOKEN, ENABLE_SCHEDULER, FRONTEND_ORIGINS
from .db import get_db, init_db
from .fetch import normalize_url
from .jobs import recover_stale_jobs, start_job
from .models import (DEFAULT_SETTINGS, Audit, Brief, BriefAction, Company, Competitor, ContextChange, Document,
                     InterviewTurn, JobRun, ProfileFact, Signal, Source, SourceCheck, Upload, now)
from .pipelines import (audit_job, context_job, crawl_only_job, research_job, stack_job, upload_job,
                        weekly_brief_job)
from .services import interview as iv
from .services.brief import to_email_html
from .services.internal import save_upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = FastAPI(title="Signal Stack API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS + ["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _startup():
    init_db()
    recover_stale_jobs()
    if ENABLE_SCHEDULER:
        scheduler.start()


def row(o, exclude=()) -> dict:
    out = {}
    for c in inspect(o).mapper.column_attrs:
        if c.key in exclude:
            continue
        v = getattr(o, c.key)
        out[c.key] = v.isoformat() if isinstance(v, datetime) else v
    return out


def get_company(company_id: int, db: Session) -> Company:
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    return c


# ------------------------------------------------------------------ companies

class CompanyIn(BaseModel):
    name: str
    website: str


@app.get("/api/health")
def health():
    return {"ok": True, "llm_providers": llm.available_providers(), "llm_usage": llm.usage}


@app.get("/api/companies")
def list_companies(db: Session = Depends(get_db)):
    out = []
    for c in db.query(Company).order_by(Company.id).all():
        d = row(c)
        d["counts"] = {
            "sources": db.query(Source).filter(Source.company_id == c.id, Source.status == "approved").count(),
            "signals": db.query(Signal).filter(Signal.company_id == c.id).count(),
            "briefs": db.query(Brief).filter(Brief.company_id == c.id).count(),
        }
        out.append(d)
    return out


@app.post("/api/companies")
def create_company(body: CompanyIn, db: Session = Depends(get_db)):
    site = body.website.strip()
    if not site.startswith("http"):
        site = "https://" + site
    c = Company(name=body.name.strip(), website=site, settings=dict(DEFAULT_SETTINGS))
    db.add(c)
    db.commit()
    job = start_job(c.id, "research", research_job(c.id))
    if ENABLE_SCHEDULER:
        scheduler.sync_company(c)
    return {**row(c), "job_id": job}


@app.get("/api/companies/{company_id}")
def company_detail(company_id: int, db: Session = Depends(get_db)):
    c = get_company(company_id, db)
    d = row(c)
    d["next_runs"] = scheduler.next_runs(c.id) if ENABLE_SCHEDULER else {}
    return d


@app.delete("/api/companies/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    c = get_company(company_id, db)
    db.delete(c)
    db.commit()
    scheduler.remove_company(company_id)
    return {"deleted": company_id}


@app.post("/api/companies/{company_id}/research")
def rerun_research(company_id: int, db: Session = Depends(get_db)):
    get_company(company_id, db)
    return {"job_id": start_job(company_id, "research", research_job(company_id))}


@app.get("/api/companies/{company_id}/dashboard")
def dashboard(company_id: int, db: Session = Depends(get_db)):
    c = get_company(company_id, db)
    sigs = db.query(Signal).filter(Signal.company_id == c.id, Signal.dismissed.is_(False)).all()
    weeks = {}
    for s in sigs:
        wk = (s.created_at - timedelta(days=s.created_at.weekday())).date().isoformat()
        w = weeks.setdefault(wk, {"week": wk, "customers": 0, "competitors": 0, "market": 0, "internal": 0})
        w[s.category] = w.get(s.category, 0) + 1
    docs_by_day = db.query(func.date(Document.fetched_at), func.count()).filter(
        Document.company_id == c.id, ~Document.title.like("Snapshot%")).group_by(func.date(Document.fetched_at)).all()
    srcs = db.query(Source).filter(Source.company_id == c.id).all()
    last_brief = db.query(Brief).filter(Brief.company_id == c.id).order_by(Brief.id.desc()).first()
    failed = db.query(JobRun).filter(JobRun.company_id == c.id, JobRun.status == "failed").order_by(JobRun.id.desc()).limit(5).all()
    top = sorted(sigs, key=lambda s: s.score, reverse=True)[:6]
    return {
        "company": row(c),
        "kpis": {
            "signals": len(sigs), "opportunities": sum(s.signal_type == "opportunity" for s in sigs),
            "threats": sum(s.signal_type == "threat" for s in sigs),
            "documents": db.query(Document).filter(Document.company_id == c.id, ~Document.title.like("Snapshot%")).count(),
            "sources_approved": sum(s.status == "approved" for s in srcs),
            "sources_proposed": sum(s.status == "proposed" for s in srcs),
            "competitors": db.query(Competitor).filter(Competitor.company_id == c.id, Competitor.status == "approved").count(),
            "briefs": db.query(Brief).filter(Brief.company_id == c.id).count(),
        },
        "by_category": {k: sum(s.category == k for s in sigs) for k in ("customers", "competitors", "market", "internal")},
        "by_type": {k: sum(s.signal_type == k for s in sigs) for k in ("opportunity", "threat", "neutral")},
        "weekly": sorted(weeks.values(), key=lambda w: w["week"]),
        "collected_by_day": [{"day": str(d), "documents": n} for d, n in docs_by_day],
        "source_health": {h: sum(s.health == h for s in srcs if s.status == "approved")
                          for h in ("ok", "stale", "dead", "blocked", "error", "unchecked")},
        "heat": [{"category": s.category, "impact": s.impact, "urgency": s.urgency} for s in sigs],
        "top_signals": [row(s) for s in top],
        "last_brief": {"id": last_brief.id, "created_at": last_brief.created_at.isoformat()} if last_brief else None,
        "failed_jobs": [row(j) for j in failed],
        "next_runs": scheduler.next_runs(c.id) if ENABLE_SCHEDULER else {},
    }


# ------------------------------------------------------------------ profile

class FactIn(BaseModel):
    field: str
    value: str
    status: str = "founder"


@app.get("/api/companies/{company_id}/profile")
def get_profile(company_id: int, db: Session = Depends(get_db)):
    c = get_company(company_id, db)
    facts = db.query(ProfileFact).filter(ProfileFact.company_id == c.id).order_by(ProfileFact.field, ProfileFact.id).all()
    changes = db.query(ContextChange).filter(ContextChange.company_id == c.id).order_by(ContextChange.id.desc()).all()
    return {"company": row(c), "facts": [row(f) for f in facts], "context_changes": [row(x) for x in changes]}


@app.post("/api/companies/{company_id}/profile/facts")
def add_fact(company_id: int, body: FactIn, db: Session = Depends(get_db)):
    get_company(company_id, db)
    f = ProfileFact(company_id=company_id, field=body.field, value=body.value, status="founder", evidence="Edited by founder")
    db.add(f)
    db.commit()
    return row(f)


@app.put("/api/companies/{company_id}/profile/facts/{fact_id}")
def edit_fact(company_id: int, fact_id: int, body: FactIn, db: Session = Depends(get_db)):
    f = db.get(ProfileFact, fact_id)
    if not f or f.company_id != company_id:
        raise HTTPException(404)
    f.field, f.value = body.field, body.value
    if f.status != "founder":
        f.status, f.evidence = "founder", "Corrected by founder"
    db.commit()
    return row(f)


@app.delete("/api/companies/{company_id}/profile/facts/{fact_id}")
def delete_fact(company_id: int, fact_id: int, db: Session = Depends(get_db)):
    f = db.get(ProfileFact, fact_id)
    if f and f.company_id == company_id:
        db.delete(f)
        db.commit()
    return {"deleted": fact_id}


class ContextIn(BaseModel):
    change: str


@app.post("/api/companies/{company_id}/context")
def change_context(company_id: int, body: ContextIn, db: Session = Depends(get_db)):
    get_company(company_id, db)
    return {"job_id": start_job(company_id, "context_reassessment", context_job(company_id, body.change))}


# ------------------------------------------------------------------ interview

def _iv_payload(db, c):
    st = iv.state(db, c)
    return {"turns": [row(t) for t in st["turns"]], "core_done": st["core_done"], "core_total": iv.CORE_QUESTIONS,
            "complete": st["complete"], "pending": row(st["pending"]) if st["pending"] else None}


@app.get("/api/companies/{company_id}/interview")
def get_interview(company_id: int, db: Session = Depends(get_db)):
    return _iv_payload(db, get_company(company_id, db))


@app.post("/api/companies/{company_id}/interview/next")
def interview_next(company_id: int, db: Session = Depends(get_db)):
    c = get_company(company_id, db)
    iv.next_question(db, c)
    return _iv_payload(db, c)


class AnswerIn(BaseModel):
    answer: str | None = None
    skip: bool = False


@app.post("/api/companies/{company_id}/interview/{turn_id}/answer")
def interview_answer(company_id: int, turn_id: int, body: AnswerIn, db: Session = Depends(get_db)):
    c = get_company(company_id, db)
    t = db.get(InterviewTurn, turn_id)
    if not t or t.company_id != c.id:
        raise HTTPException(404)
    if not body.skip and not (body.answer or "").strip():
        raise HTTPException(400, "Answer is empty (use skip for confidential questions)")
    iv.answer(db, c, t, body.answer, body.skip)
    iv.next_question(db, c)
    return _iv_payload(db, c)


@app.put("/api/companies/{company_id}/interview/{turn_id}")
def interview_edit(company_id: int, turn_id: int, body: AnswerIn, db: Session = Depends(get_db)):
    c = get_company(company_id, db)
    t = db.get(InterviewTurn, turn_id)
    if not t or t.company_id != c.id:
        raise HTTPException(404)
    iv.edit_answer(db, c, t, body.answer, body.skip)
    return _iv_payload(db, c)


# ------------------------------------------------------------------ signal stack / sources

@app.post("/api/companies/{company_id}/stack/build")
def build_stack(company_id: int, db: Session = Depends(get_db)):
    get_company(company_id, db)
    return {"job_id": start_job(company_id, "build_signal_stack", stack_job(company_id))}


@app.get("/api/companies/{company_id}/competitors")
def competitors(company_id: int, db: Session = Depends(get_db)):
    out = []
    for c in db.query(Competitor).filter(Competitor.company_id == company_id).order_by(Competitor.id).all():
        d = row(c)
        d["signals"] = db.query(Signal).filter(Signal.competitor_id == c.id).count()
        d["sources"] = db.query(Source).filter(Source.competitor_id == c.id, Source.status == "approved").count()
        out.append(d)
    return out


class CompetitorPatch(BaseModel):
    status: str


@app.patch("/api/companies/{company_id}/competitors/{cid}")
def patch_competitor(company_id: int, cid: int, body: CompetitorPatch, db: Session = Depends(get_db)):
    c = db.get(Competitor, cid)
    if not c or c.company_id != company_id:
        raise HTTPException(404)
    c.status = body.status
    if body.status == "removed":
        for s in db.query(Source).filter(Source.competitor_id == cid):
            s.status, s.removed_reason = "removed", "Competitor removed by founder"
    db.commit()
    return row(c)


@app.get("/api/companies/{company_id}/sources")
def sources(company_id: int, db: Session = Depends(get_db)):
    return [row(s) for s in db.query(Source).filter(Source.company_id == company_id).order_by(Source.category, Source.id).all()]


class SourceIn(BaseModel):
    category: str
    name: str
    url: str = ""
    query: str = ""
    reason: str


@app.post("/api/companies/{company_id}/sources")
def add_source(company_id: int, body: SourceIn, db: Session = Depends(get_db)):
    from .discovery_helpers import classify_manual_source
    get_company(company_id, db)
    if body.query:
        kind, url = "news_query", f"news://{body.query}"
    else:
        kind, url = classify_manual_source(body.url)
    dup = [s for s in db.query(Source).filter(Source.company_id == company_id)
           if (s.kind == "news_query" and s.query.lower() == body.query.lower() and body.query)
           or (not body.query and normalize_url(s.url) == normalize_url(url))]
    if dup:
        raise HTTPException(409, f"Duplicate of existing source '{dup[0].name}'")
    s = Source(company_id=company_id, category=body.category, kind=kind, name=body.name, url=url, query=body.query,
               reason=body.reason, status="approved", discovered_by="founder", specific=0.8, recent=0.6, credible=0.7)
    db.add(s)
    db.commit()
    return row(s)


class SourcePatch(BaseModel):
    status: str | None = None
    reason: str | None = None
    category: str | None = None


@app.patch("/api/companies/{company_id}/sources/{sid}")
def patch_source(company_id: int, sid: int, body: SourcePatch, db: Session = Depends(get_db)):
    s = db.get(Source, sid)
    if not s or s.company_id != company_id:
        raise HTTPException(404)
    if body.status:
        s.status = body.status
        if body.status == "removed":
            s.removed_reason = s.removed_reason or "Removed by founder"
    if body.reason is not None:
        s.reason = body.reason
    if body.category:
        s.category = body.category
    db.commit()
    return row(s)


@app.get("/api/companies/{company_id}/sources/{sid}/history")
def source_history(company_id: int, sid: int, db: Session = Depends(get_db)):
    s = db.get(Source, sid)
    if not s or s.company_id != company_id:
        raise HTTPException(404)
    checks = db.query(SourceCheck).filter(SourceCheck.source_id == sid).order_by(SourceCheck.id.desc()).limit(50).all()
    docs = db.query(Document).filter(Document.source_id == sid, ~Document.title.like("Snapshot%")) \
        .order_by(Document.id.desc()).limit(30).all()
    return {"source": row(s), "checks": [row(c) for c in checks],
            "documents": [row(d, exclude=("text",)) for d in docs]}


# ------------------------------------------------------------------ monitoring / signals

@app.post("/api/companies/{company_id}/crawl")
def crawl(company_id: int, lookback: int | None = None, db: Session = Depends(get_db)):
    get_company(company_id, db)
    return {"job_id": start_job(company_id, "monitoring_crawl", crawl_only_job(company_id, lookback))}


@app.get("/api/companies/{company_id}/signals")
def signals(company_id: int, category: str | None = None, competitor_id: int | None = None,
            signal_type: str | None = None, verification: str | None = None, min_relevance: float = 0,
            min_impact: int = 0, since: str | None = None, until: str | None = None, sort: str = "date",
            limit: int = 200, db: Session = Depends(get_db)):
    q = db.query(Signal).filter(Signal.company_id == company_id, Signal.dismissed.is_(False))
    if category:
        q = q.filter(Signal.category == category)
    if competitor_id:
        q = q.filter(Signal.competitor_id == competitor_id)
    if signal_type:
        q = q.filter(Signal.signal_type == signal_type)
    if verification:
        q = q.filter(Signal.verification == verification)
    if min_relevance:
        q = q.filter(Signal.relevance >= min_relevance)
    if min_impact:
        q = q.filter(Signal.impact >= min_impact)
    if since:
        q = q.filter(Signal.created_at >= datetime.fromisoformat(since))
    if until:
        q = q.filter(Signal.created_at <= datetime.fromisoformat(until) + timedelta(days=1))
    q = q.order_by(Signal.score.desc() if sort == "score" else Signal.created_at.desc())
    out = []
    docs = {}
    for s in q.limit(limit).all():
        d = docs.get(s.document_id) or db.get(Document, s.document_id)
        docs[s.document_id] = d
        r = row(s)
        r["source_url"] = d.url if d else ""
        r["publisher"] = d.publisher if d else ""
        r["published_at"] = d.published_at.isoformat() if d and d.published_at else None
        r["fetched_at"] = d.fetched_at.isoformat() if d else None
        r["full_text"] = bool(d and d.full_text)
        out.append(r)
    return out


@app.post("/api/companies/{company_id}/signals/{sid}/dismiss")
def dismiss_signal(company_id: int, sid: int, db: Session = Depends(get_db)):
    s = db.get(Signal, sid)
    if not s or s.company_id != company_id:
        raise HTTPException(404)
    s.dismissed = True
    db.commit()
    return {"dismissed": sid}


@app.get("/api/companies/{company_id}/documents")
def documents(company_id: int, limit: int = 100, db: Session = Depends(get_db)):
    ds = db.query(Document).filter(Document.company_id == company_id, ~Document.title.like("Snapshot%")) \
        .order_by(Document.id.desc()).limit(limit).all()
    return [row(d, exclude=("text",)) | {"preview": d.text[:300]} for d in ds]


# ------------------------------------------------------------------ uploads

@app.post("/api/companies/{company_id}/uploads")
async def upload(company_id: int, file: UploadFile = File(...), label: str = Form(""), db: Session = Depends(get_db)):
    c = get_company(company_id, db)
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "File too large (15MB max)")
    try:
        up = save_upload(db, c, file.filename, data, label)
    except ValueError as e:
        raise HTTPException(400, str(e))
    job = start_job(company_id, "internal_analysis", upload_job(company_id, up.id))
    return {**row(up), "job_id": job}


@app.get("/api/companies/{company_id}/uploads")
def uploads(company_id: int, db: Session = Depends(get_db)):
    out = []
    for u in db.query(Upload).filter(Upload.company_id == company_id).order_by(Upload.id.desc()).all():
        r = row(u)
        r["insights"] = db.query(Signal).filter(Signal.document_id == u.document_id).count()
        out.append(r)
    return out


# ------------------------------------------------------------------ briefs

@app.post("/api/companies/{company_id}/briefs/run")
def run_brief(company_id: int, lookback: int | None = None, db: Session = Depends(get_db)):
    get_company(company_id, db)
    return {"job_id": start_job(company_id, "weekly_brief", weekly_brief_job(company_id, "manual", lookback))}


@app.get("/api/companies/{company_id}/briefs")
def briefs(company_id: int, db: Session = Depends(get_db)):
    return [row(b, exclude=("content", "markdown")) | {"stats": b.content.get("stats", {})}
            for b in db.query(Brief).filter(Brief.company_id == company_id).order_by(Brief.id.desc()).all()]


@app.get("/api/briefs/{brief_id}")
def brief(brief_id: int, db: Session = Depends(get_db)):
    b = db.get(Brief, brief_id)
    if not b:
        raise HTTPException(404)
    acts = db.query(BriefAction).filter(BriefAction.brief_id == b.id).order_by(BriefAction.id).all()
    return row(b) | {"actions": [row(a) for a in acts]}


@app.get("/api/briefs/{brief_id}/export.md", response_class=PlainTextResponse)
def brief_md(brief_id: int, db: Session = Depends(get_db)):
    b = db.get(Brief, brief_id)
    if not b:
        raise HTTPException(404)
    return PlainTextResponse(b.markdown, headers={"Content-Disposition": f'attachment; filename="monday-brief-{brief_id}.md"'})


@app.get("/api/briefs/{brief_id}/export.html", response_class=HTMLResponse)
def brief_html(brief_id: int, db: Session = Depends(get_db)):
    b = db.get(Brief, brief_id)
    if not b:
        raise HTTPException(404)
    return HTMLResponse(to_email_html(b.markdown))


class ActionPatch(BaseModel):
    status: str | None = None
    owner: str | None = None


@app.patch("/api/actions/{action_id}")
def patch_action(action_id: int, body: ActionPatch, db: Session = Depends(get_db)):
    a = db.get(BriefAction, action_id)
    if not a:
        raise HTTPException(404)
    if body.status:
        a.status = body.status
    if body.owner is not None:
        a.owner = body.owner
    db.commit()
    return row(a)


# ------------------------------------------------------------------ audits, jobs, settings

@app.post("/api/companies/{company_id}/audit/run")
def run_audit(company_id: int, db: Session = Depends(get_db)):
    get_company(company_id, db)
    return {"job_id": start_job(company_id, "monthly_audit", audit_job(company_id))}


@app.get("/api/companies/{company_id}/audits")
def audits(company_id: int, db: Session = Depends(get_db)):
    return [row(a) for a in db.query(Audit).filter(Audit.company_id == company_id).order_by(Audit.id.desc()).all()]


@app.get("/api/jobs")
def jobs(company_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(JobRun)
    if company_id:
        q = q.filter(JobRun.company_id == company_id)
    return [row(j) for j in q.order_by(JobRun.id.desc()).limit(limit).all()]


@app.get("/api/jobs/{job_id}")
def job(job_id: int, db: Session = Depends(get_db)):
    j = db.get(JobRun, job_id)
    if not j:
        raise HTTPException(404)
    return row(j)


class SettingsIn(BaseModel):
    briefing_day: str | None = None
    briefing_time: str | None = None
    timezone: str | None = None
    monitoring_frequency_hours: int | None = None
    source_refresh_days: int | None = None
    audit_day_of_month: int | None = None
    lookback_days: int | None = None


@app.put("/api/companies/{company_id}/settings")
def update_settings(company_id: int, body: SettingsIn, db: Session = Depends(get_db)):
    c = get_company(company_id, db)
    s = dict(c.settings or DEFAULT_SETTINGS)
    s.update({k: v for k, v in body.model_dump().items() if v is not None})
    c.settings = s
    db.commit()
    if ENABLE_SCHEDULER:
        scheduler.sync_company(c)
    return {"settings": c.settings, "next_runs": scheduler.next_runs(c.id) if ENABLE_SCHEDULER else {}}


# ------------------------------------------------------------------ external cron (free GitHub Actions)

@app.post("/api/cron/{kind}")
def cron(kind: str, x_cron_token: str = Header(""), db: Session = Depends(get_db)):
    """Lets a free external scheduler trigger runs when the free host was asleep at the scheduled time."""
    if not CRON_TOKEN or x_cron_token != CRON_TOKEN:
        raise HTTPException(401, "Invalid cron token")
    started = []
    for c in db.query(Company).all():
        if kind == "weekly":
            started.append(start_job(c.id, "weekly_brief", weekly_brief_job(c.id, "cron", 10), "cron"))
        elif kind == "audit":
            started.append(start_job(c.id, "monthly_audit", audit_job(c.id), "cron"))
        else:
            raise HTTPException(400, "kind must be weekly or audit")
    return {"started_jobs": started}
