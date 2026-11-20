"""Background job runner. Every run (manual, scheduled, external cron) is logged in job_runs so
failures are visible in the dashboard."""
import logging
import threading
import traceback

from .db import session_scope
from .models import JobRun, now

log = logging.getLogger("jobs")
_company_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(company_id):
    with _locks_guard:
        return _company_locks.setdefault(company_id or 0, threading.Lock())


class JobContext:
    def __init__(self, job_id: int):
        self.job_id = job_id
        self.stats: dict = {}

    def progress(self, msg: str):
        log.info("[job %s] %s", self.job_id, msg)
        with session_scope() as db:
            j = db.get(JobRun, self.job_id)
            j.progress = msg[:500]
            j.stats = dict(self.stats)


_running = 0
_running_lock = threading.Lock()


def _keep_awake():
    """Free hosts (Render) stop an idle instance after ~15 min without inbound HTTP traffic, which would kill a
    long crawl. While any job runs, ping our own public URL so the instance stays up until the job finishes."""
    import os
    import time

    import httpx
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("PUBLIC_API_URL")
    if not url:
        return
    while True:
        time.sleep(240)
        with _running_lock:
            if _running == 0:
                return
        try:
            httpx.get(url.rstrip("/") + "/api/health", timeout=20)
        except httpx.HTTPError:
            pass


def start_job(company_id, job_type: str, fn, trigger: str = "manual", background: bool = True) -> int:
    """fn(ctx) does the work. Returns job id. Only one heavy job per company at a time."""
    with session_scope() as db:
        j = JobRun(company_id=company_id, job_type=job_type, trigger=trigger, status="queued", progress="Queued")
        db.add(j)
        db.flush()
        job_id = j.id

    def run():
        global _running
        with _running_lock:
            _running += 1
            first = _running == 1
        if first:
            threading.Thread(target=_keep_awake, daemon=True, name="keep-awake").start()
        try:
            _run_locked()
        finally:
            with _running_lock:
                _running -= 1

    def _run_locked():
        lock = _lock_for(company_id)
        with lock:
            ctx = JobContext(job_id)
            with session_scope() as db:
                j = db.get(JobRun, job_id)
                j.status, j.started_at, j.progress = "running", now(), "Started"
            try:
                fn(ctx)
                status, err = ("partial" if ctx.stats.get("errors") else "success"), ""
            except Exception as e:  # recorded, never swallowed silently
                log.exception("job %s failed", job_id)
                status, err = "failed", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-2000:]}"
            with session_scope() as db:
                j = db.get(JobRun, job_id)
                j.status, j.error, j.finished_at, j.stats = status, err, now(), dict(ctx.stats)
                if status != "failed":
                    j.progress = "Done"

    if background:
        threading.Thread(target=run, daemon=True, name=f"job-{job_id}").start()
    else:
        run()
    return job_id


def recover_stale_jobs():
    """On startup, any job still 'running' was killed by a restart: mark it failed (visible in UI)."""
    with session_scope() as db:
        for j in db.query(JobRun).filter(JobRun.status.in_(["running", "queued"])).all():
            j.status, j.finished_at = "failed", now()
            j.error = "Interrupted: the server restarted while this job was running."
