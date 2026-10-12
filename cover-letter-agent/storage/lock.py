"""One computer at a time when the data is in a synced folder (SYNC_FOLDER in .env).

The database is a single file. If two computers changed it at once, the sync service would
keep one copy and set the other aside, losing work. So the computer running the app writes
data/app.lock (its name and a heartbeat every minute), and another computer that finds a
fresh lock from someone else waits instead of starting. Quit app removes the lock at once;
a window closed without quitting leaves a lock that goes stale after a few minutes.
"""

import atexit
import json
import os
import socket
import threading
import time

import config

HEARTBEAT = 60   # seconds between heartbeats
STALE = 180      # a lock older than this is from a computer that stopped without quitting

_held = False
_thread: threading.Thread | None = None
_guard = threading.Lock()


def path():
    return config.DATA_DIR / "app.lock"


def _host() -> str:
    return socket.gethostname()


def read() -> dict | None:
    try:
        return json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def holder(now: float | None = None) -> dict | None:
    """The other computer that has the app open: its lock, with 'age' in seconds. None if
    the lock is missing, this computer's own, or stale."""
    data = read()
    if not data or data.get("host") == _host():
        return None
    age = (now or time.time()) - float(data.get("beat", 0))
    return {**data, "age": max(age, 0)} if age <= STALE else None


def _write() -> None:
    path().parent.mkdir(parents=True, exist_ok=True)
    tmp = path().with_suffix(".lock.tmp")
    tmp.write_text(json.dumps({"host": _host(), "pid": os.getpid(), "beat": time.time()}), encoding="utf-8")
    tmp.replace(path())


def _beat() -> None:
    while _held:
        time.sleep(HEARTBEAT)
        if _held:
            try:
                _write()
            except OSError:
                pass  # the folder is briefly busy (the sync service); the next beat tries again


def held() -> bool:
    return _held


def acquire() -> None:
    """Take the lock for this computer and keep it fresh while the app runs."""
    global _held, _thread
    with _guard:
        _write()
        if _held:
            return
        _held = True
        _thread = threading.Thread(target=_beat, name="app-lock", daemon=True)
        _thread.start()
        atexit.register(release)


def release() -> None:
    """Remove the lock if it's this computer's, so the other computer can start right away."""
    global _held
    with _guard:
        _held = False
        data = read()
        if data and data.get("host") == _host():
            try:
                path().unlink()
            except OSError:
                pass
