"""Daily scheduled run (Milestone 12), with Adzuna and Claude faked."""

import threading
from datetime import datetime, time

import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from search import run, schedule
from storage import jobs as store
from tests.test_search import NOW, FakeAdzuna, criteria, ready, saved  # noqa: F401 - ready is a fixture
from ui.find_jobs import schedule_status


@pytest.fixture(autouse=True)
def no_live_scheduler(monkeypatch):
    monkeypatch.setattr(schedule, "_scheduler", None)


def test_settings_default_and_save(ready):
    assert schedule.settings() == {"enabled": False, "time": "07:00", "last": None}
    schedule.save(True, time(6, 30))
    assert schedule.settings()["enabled"] and schedule.settings()["time"] == "06:30"


def test_scheduled_run_adds_only_new_jobs(ready):
    saved(criteria())
    first = schedule.run_now(now=NOW, client=FakeAdzuna().client())
    assert first["ok"] and first["new"] == 8 and "6 Adzuna calls" in first["message"]
    second = schedule.run_now(now=NOW, client=FakeAdzuna().client())
    assert second["ok"] and second["new"] == 0
    assert store.count_jobs()["new"] == 8
    assert schedule.settings()["last"] == second  # the outcome is kept for the Find jobs screen


def test_run_now_records_problems_instead_of_raising(ready, monkeypatch):
    assert schedule.run_now(now=NOW)["message"] == "No saved searches to run."
    saved(criteria())

    def over_limit(*a, **k):
        raise run.UsageLimit("This run needs 6 Adzuna calls and 248 of today's 250 are used.")

    monkeypatch.setattr(run, "run_searches", over_limit)
    outcome = schedule.run_now(now=NOW)
    assert not outcome["ok"] and "248 of today's 250" in outcome["message"]
    monkeypatch.setattr(run, "run_searches", lambda *a, **k: 1 / 0)
    assert "The scheduled run failed" in schedule.run_now(now=NOW)["message"]


def test_only_one_search_at_a_time(ready):
    saved(criteria())
    with schedule.exclusive() as free:
        assert free
        outcome = schedule.run_now(now=NOW)
    assert outcome["message"] == "A search was already running." and store.count_jobs()["new"] == 0
    with schedule.exclusive() as free:
        assert free  # released again


def test_missed_run(ready):
    search_id = saved(criteria())["id"]
    morning = datetime(2026, 10, 1, 7, 0)
    assert not schedule.missed(datetime(2026, 10, 1, 9, 0))  # schedule is off
    schedule.save(True, time(7, 0))
    assert not schedule.missed(datetime(2026, 10, 1, 6, 0))  # not time yet
    assert schedule.missed(datetime(2026, 10, 1, 9, 0))  # never ran
    store.mark_run(search_id, datetime(2026, 9, 30, 20, 0).isoformat())
    assert schedule.missed(datetime(2026, 10, 1, 9, 0))  # last run was yesterday
    store.mark_run(search_id, morning.replace(hour=8).isoformat())
    assert not schedule.missed(datetime(2026, 10, 1, 9, 0))  # already ran today after 7:00


def test_apply_schedules_and_catches_up(ready):
    saved(criteria())
    scheduler = BackgroundScheduler()  # not started: jobs are listed but never run
    schedule.apply(scheduler, now=datetime(2026, 10, 1, 6, 0))
    assert scheduler.get_jobs() == []  # off
    schedule.save(True, time(7, 15))
    schedule.apply(scheduler, now=datetime(2026, 10, 1, 6, 0))
    job = scheduler.get_job(schedule.JOB_ID)
    assert str(job.trigger) == "cron[hour='7', minute='15']" and job.misfire_grace_time == schedule.GRACE
    assert scheduler.get_job("catch_up") is None
    schedule.apply(scheduler, now=datetime(2026, 10, 1, 9, 0))
    assert scheduler.get_job("catch_up") is not None  # 7:15 passed with no run: run right away
    schedule.save(False, time(7, 15))
    schedule.apply(scheduler)
    assert scheduler.get_job(schedule.JOB_ID) is None


def test_ensure_started_once(ready, monkeypatch):
    started = []
    monkeypatch.setattr(BackgroundScheduler, "start", lambda self: started.append(self))
    threads = [threading.Thread(target=schedule.ensure_started) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(started) == 1


def test_schedule_status_text():
    off = schedule_status({"enabled": False, "time": "07:00", "last": None}, None)
    assert off.startswith("Off.")
    today = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
    on = schedule_status({"enabled": True, "time": "07:00", "last": {
        "at": today.isoformat(), "ok": True, "new": 3, "message": "..."}}, None)
    assert on == "Every day at 7:00 AM while the app is running. Last daily run today at 7:00 AM: 3 new jobs."
    failed = schedule_status({"enabled": True, "time": "19:30", "last": {
        "at": today.isoformat(), "ok": False, "message": "No saved searches to run."}}, None)
    assert "Every day at 7:30 PM" in failed and failed.endswith("No saved searches to run.")
