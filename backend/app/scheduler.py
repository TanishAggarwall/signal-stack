"""Two independent automated processes per company, using each company's own settings:
  A. weekly brief  (cron: briefing_day + briefing_time in the company's time zone)
  B. monthly audit (cron: audit_day_of_month)
plus optional interval monitoring crawls. Missed runs (server asleep) are logged as failed job runs."""
import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .db import session_scope
from .jobs import start_job
from .models import Company, JobRun, now
from .pipelines import audit_job, crawl_only_job, weekly_brief_job

log = logging.getLogger("scheduler")
scheduler = BackgroundScheduler(job_defaults={"coalesce": True, "misfire_grace_time": 3600})


def _run(kind: str, company_id: int):
    if kind == "weekly":
        start_job(company_id, "weekly_brief", weekly_brief_job(company_id, trigger="schedule", lookback=10), "schedule")
    elif kind == "audit":
        start_job(company_id, "monthly_audit", audit_job(company_id), "schedule")
    elif kind == "monitor":
        start_job(company_id, "monitoring_crawl", crawl_only_job(company_id, lookback=10), "schedule")


def _missed(event):
    """APScheduler could not run a job on time (e.g. the free host was asleep): make it visible."""
    try:
        kind, cid = event.job_id.split(":")[0], int(event.job_id.split(":")[1])
    except (ValueError, IndexError):
        return
    with session_scope() as db:
        db.add(JobRun(company_id=cid, job_type={"weekly": "weekly_brief", "audit": "monthly_audit"}.get(kind, kind),
                      trigger="schedule", status="failed", finished_at=now(),
                      error=f"Scheduled run missed at {event.scheduled_run_time} (server unavailable)."))


def sync_company(company: Company):
    s = company.settings or {}
    tz = s.get("timezone", "Asia/Kolkata")
    hh, mm = (s.get("briefing_time", "07:00").split(":") + ["0"])[:2]
    try:
        scheduler.add_job(_run, CronTrigger(day_of_week=s.get("briefing_day", "mon"), hour=int(hh), minute=int(mm), timezone=tz),
                          args=["weekly", company.id], id=f"weekly:{company.id}", replace_existing=True)
        scheduler.add_job(_run, CronTrigger(day=int(s.get("audit_day_of_month", 1)), hour=int(hh), minute=int(mm), timezone=tz),
                          args=["audit", company.id], id=f"audit:{company.id}", replace_existing=True)
        hours = int(s.get("monitoring_frequency_hours", 24))
        if 0 < hours < 168:
            scheduler.add_job(_run, IntervalTrigger(hours=hours, start_date=now() + timedelta(hours=hours)),
                              args=["monitor", company.id], id=f"monitor:{company.id}", replace_existing=True)
        elif scheduler.get_job(f"monitor:{company.id}"):
            scheduler.remove_job(f"monitor:{company.id}")
    except Exception:
        log.exception("could not schedule company %s", company.id)


def remove_company(company_id: int):
    for k in ("weekly", "audit", "monitor"):
        if scheduler.get_job(f"{k}:{company_id}"):
            scheduler.remove_job(f"{k}:{company_id}")


def start():
    from apscheduler.events import EVENT_JOB_MISSED
    scheduler.add_listener(_missed, EVENT_JOB_MISSED)
    with session_scope() as db:
        for c in db.query(Company).all():
            sync_company(c)
    scheduler.start()


def next_runs(company_id: int) -> dict:
    out = {}
    for k in ("weekly", "audit", "monitor"):
        j = scheduler.get_job(f"{k}:{company_id}")
        out[k] = j.next_run_time.isoformat() if j and j.next_run_time else None
    return out
