"""Daily scheduled run (spec: Running it; Milestone 12).

APScheduler runs inside the app's server process, so runs happen while the app is
running. If the day's time passed while the app was closed (or the computer was asleep),
the run happens as soon as the app is open again, unless a search already ran since.
"""

import json
import threading
from contextlib import contextmanager
from datetime import datetime, time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from search import adzuna, run
from storage import jobs as store

JOB_ID = "daily_search"
DEFAULT_TIME = "07:00"
GRACE = 6 * 3600  # a run missed while the computer slept still happens within 6 hours

_run_lock = threading.Lock()
_start_lock = threading.Lock()
_scheduler: BackgroundScheduler | None = None


def settings() -> dict:
    """enabled, time ("HH:MM") and the last scheduled run's outcome (or None)."""
    last = store.get_setting("schedule_last")
    return {"enabled": store.get_setting("schedule_enabled") == "1",
            "time": store.get_setting("schedule_time", DEFAULT_TIME),
            "last": json.loads(last) if last else None}


def save(enabled: bool, at: time) -> None:
    store.set_setting("schedule_enabled", "1" if enabled else "0")
    store.set_setting("schedule_time", at.strftime("%H:%M"))
    if _scheduler:
        apply(_scheduler)


def _record(outcome: dict) -> dict:
    store.set_setting("schedule_last", json.dumps(outcome))
    return outcome


@contextmanager
def exclusive():
    """Yields True if no other search is running (scheduled or on demand), holding the
    lock until the block ends; False if one is."""
    got = _run_lock.acquire(blocking=False)
    try:
        yield got
    finally:
        if got:
            _run_lock.release()


def run_now(now: datetime | None = None, **run_args) -> dict:
    """Run every saved search, as the schedule does, and record the outcome. Never raises:
    a scheduler thread has nobody to show an error to, so it goes in the record."""
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    with exclusive() as free:
        if not free:
            return {"at": stamp, "ok": False, "message": "A search was already running."}
        return _run_all(stamp, now, run_args)


def _run_all(stamp: str, now: datetime | None, run_args: dict) -> dict:
    try:
        searches = store.list_searches()
        if not searches:
            return _record({"at": stamp, "ok": False, "message": "No saved searches to run."})
        result = run.run_searches(searches, now=now, **run_args)
        return _record({"at": result.finished_at, "ok": True, "new": result.new,
                        "message": result.summary(), "errors": result.errors})
    except (run.UsageLimit, adzuna.AdzunaError) as exc:
        return _record({"at": stamp, "ok": False, "message": str(exc)})
    except Exception as exc:  # noqa: BLE001 - keep the scheduler alive and say what happened
        return _record({"at": stamp, "ok": False, "message": f"The scheduled run failed: {exc}"})


def missed(now: datetime | None = None) -> bool:
    """True if today's run time has passed and no search has run since then."""
    s = settings()
    if not s["enabled"]:
        return False
    now = now or datetime.now()
    due = datetime.combine(now.date(), time.fromisoformat(s["time"]))
    if now < due:
        return False
    runs = [x["last_run_at"] for x in store.list_searches() if x["last_run_at"]]
    return not runs or datetime.fromisoformat(max(runs)) < due


def apply(scheduler: BackgroundScheduler, now: datetime | None = None) -> None:
    """Match the scheduler to the saved settings, and catch up on a missed run."""
    s = settings()
    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)
    if s["enabled"]:
        hour, minute = (int(part) for part in s["time"].split(":"))
        scheduler.add_job(run_now, CronTrigger(hour=hour, minute=minute), id=JOB_ID,
                          misfire_grace_time=GRACE, coalesce=True, max_instances=1)
        if missed(now):
            scheduler.add_job(run_now, id="catch_up", replace_existing=True)  # runs right away


def ensure_started() -> BackgroundScheduler:
    """Start the scheduler once per server process."""
    global _scheduler
    with _start_lock:
        if _scheduler is None:
            _scheduler = BackgroundScheduler(daemon=True)
            _scheduler.start()
            apply(_scheduler)
        return _scheduler


def next_run() -> datetime | None:
    job = _scheduler.get_job(JOB_ID) if _scheduler else None
    return job.next_run_time.replace(tzinfo=None) if job and job.next_run_time else None
