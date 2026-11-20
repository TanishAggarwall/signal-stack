"""Job bodies used by the API, the in-process scheduler and the external cron endpoint."""
from .db import SessionLocal
from .models import Audit, Company


def _with_company(company_id, fn):
    def run(ctx):
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                raise ValueError(f"Company {company_id} not found")
            fn(db, company, ctx)
        finally:
            db.close()
    return run


def research_job(company_id):
    from .services.research import run_research

    def body(db, company, ctx):
        ctx.stats.update(run_research(db, company, ctx.progress))
    return _with_company(company_id, body)


def stack_job(company_id):
    from .services.discovery import build_signal_stack

    def body(db, company, ctx):
        ctx.stats.update(build_signal_stack(db, company, ctx.progress))
    return _with_company(company_id, body)


def weekly_brief_job(company_id, trigger="manual", lookback=None):
    """A. Weekly Intelligence Brief: crawl approved sources -> detect changes -> analyse -> rank -> brief."""
    from .services.analysis import analyze_documents
    from .services.brief import generate_brief
    from .services.crawler import crawl_company
    from .services.internal import analyze_pending_uploads
    from .services.ranking import rank_signals

    def body(db, company, ctx):
        ctx.stats["crawl"] = crawl_company(db, company, ctx.progress, job_id=ctx.job_id, lookback=lookback)
        ctx.progress("Analysing internal uploads")
        ctx.stats["internal"] = analyze_pending_uploads(db, company, ctx.progress)
        ctx.stats["analysis"] = analyze_documents(db, company, ctx.progress)
        if ctx.stats["analysis"].get("llm_errors"):
            ctx.stats["errors"] = ctx.stats["analysis"]["llm_errors"]
        ctx.progress("Ranking signals")
        rank_signals(db, company)
        brief = generate_brief(db, company, trigger=trigger, job_id=ctx.job_id, progress=ctx.progress)
        ctx.stats["brief_id"] = brief.id
    return _with_company(company_id, body)


def crawl_only_job(company_id, lookback=None):
    from .services.analysis import analyze_documents
    from .services.crawler import crawl_company
    from .services.ranking import rank_signals

    def body(db, company, ctx):
        ctx.stats["crawl"] = crawl_company(db, company, ctx.progress, job_id=ctx.job_id, lookback=lookback)
        ctx.stats["analysis"] = analyze_documents(db, company, ctx.progress)
        rank_signals(db, company)
    return _with_company(company_id, body)


def audit_job(company_id):
    """B. Monthly Signal Stack Audit."""
    from .services.audit import run_audit

    def body(db, company, ctx):
        report = run_audit(db, company, ctx.progress)
        db.add(Audit(company_id=company.id, report=report, job_id=ctx.job_id))
        db.commit()
        ctx.stats.update({k: len(v) for k, v in report.items() if isinstance(v, list)})
    return _with_company(company_id, body)


def context_job(company_id, change_text):
    from .services.audit import reassess_context

    def body(db, company, ctx):
        r = reassess_context(db, company, change_text, ctx.progress)
        ctx.stats.update({"no_longer_useful": len(r["no_longer_useful"]), "new_sources": len(r["new_sources"])})
    return _with_company(company_id, body)


def upload_job(company_id, upload_id):
    from .models import Upload
    from .services.internal import analyze_upload

    def body(db, company, ctx):
        ctx.stats.update(analyze_upload(db, company, db.get(Upload, upload_id), ctx.progress))
    return _with_company(company_id, body)
