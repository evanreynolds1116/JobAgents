"""Using the app on two computers through a synced folder: SYNC_FOLDER, the one-computer-
at-a-time lock and Quit app."""

import json
import os
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import config
from storage import lock

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def synced(app_paths, monkeypatch):
    """Sync turned on, with the lock released afterwards so no heartbeat outlives the test."""
    monkeypatch.setattr(config, "SYNC_FOLDER", app_paths / "OneDrive" / "JobAgents")
    monkeypatch.setattr(lock, "HEARTBEAT", 3600)
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n")
    yield app_paths
    lock.release()


def other_computer(age=10):
    lock.path().parent.mkdir(parents=True, exist_ok=True)
    lock.path().write_text(json.dumps({"host": "EVANS-MACBOOK", "pid": 1, "beat": time.time() - age}))


def run_app():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def test_sync_folder_setting(tmp_path):
    env = tmp_path / ".env"
    assert config.sync_folder(env) is None
    env.write_text("SYNC_FOLDER=\n")
    assert config.sync_folder(env) is None
    env.write_text("SYNC_FOLDER=~/Library/CloudStorage/OneDrive-Personal/JobAgents\n")
    assert config.sync_folder(env) == Path.home() / "Library/CloudStorage/OneDrive-Personal/JobAgents"


def test_lock_rules(synced):
    assert lock.holder() is None                   # no lock yet
    other_computer(age=30)
    assert lock.holder()["host"] == "EVANS-MACBOOK" and 29 <= lock.holder()["age"] <= 40
    other_computer(age=lock.STALE + 5)
    assert lock.holder() is None                   # stopped without quitting: stale
    lock.acquire()
    assert lock.read()["host"] == lock._host() and lock.holder() is None  # our own lock
    lock.release()
    assert not lock.path().exists()
    other_computer()
    lock.release()                                 # never removes another computer's lock
    assert lock.read()["host"] == "EVANS-MACBOOK"


def test_waits_while_open_on_the_other_computer(synced):
    other_computer()
    at = run_app()
    assert at.title[0].value == "Open on another computer"
    assert "EVANS-MACBOOK" in at.markdown[0].value
    assert not config.DB_PATH.exists()             # nothing touched the shared data
    lock.path().unlink()                           # quit there
    [b for b in at.button if b.label == "Check again"][0].click().run()
    assert at.title[0].value == "New cover letter" and lock.held()
    assert lock.read()["host"] == lock._host() and config.DB_PATH.exists()


def test_open_anyway(synced):
    other_computer()
    at = run_app()
    [b for b in at.button if b.label == "Open anyway"][0].click().run()
    assert at.title[0].value == "New cover letter" and lock.read()["host"] == lock._host()


def test_quit_releases_the_lock(synced, monkeypatch):
    stopped = []
    monkeypatch.setattr(os, "_exit", lambda code: stopped.append(code))
    at = run_app()
    assert lock.read()["host"] == lock._host()
    [b for b in at.button if b.label == "Quit app"][0].click().run()
    assert at.title[0].value == "The app has stopped" and not lock.path().exists()
    time.sleep(1.5)
    assert stopped == [0]


def test_without_sync_there_is_no_lock(app_paths):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n")
    run_app()
    assert not lock.path().exists() and not lock.held()


def test_chrome_profile_and_upload_copy_stay_on_this_computer(synced):
    from storage import resume

    (config.DATA_DIR).mkdir(parents=True)
    (config.DATA_DIR / "resume_original.pdf").write_bytes(b"%PDF-1.4 test")
    copy = resume.upload_file("Evan Reynolds")
    assert copy.parent == config.LOCAL_DIR / "upload" and config.SYNC_FOLDER not in copy.parents
