"""SQLite schema and connection for data/app.db.

Tables follow the spec's Data & storage section. Phase 2 and 3 tables
(saved_answers, filled_answers, saved_searches, jobs) are added in their own milestones.
"""

import json
import sqlite3
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import config

STATUSES = ("draft", "approved", "submitted", "archived")

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS applications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT,
    company       TEXT,
    title         TEXT,
    posting_text  TEXT,
    user_notes    TEXT,
    parsed_json   TEXT,
    match_json    TEXT,
    status        TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ({", ".join(f"'{s}'" for s in STATUSES)})),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    approved_at   TEXT,
    submitted_at  TEXT,
    sent_version  INTEGER,
    notes         TEXT NOT NULL DEFAULT '[]'  -- JSON list of {{"date": ..., "text": ...}}
);

CREATE INDEX IF NOT EXISTS idx_applications_url ON applications (url);

CREATE TABLE IF NOT EXISTS drafts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id  INTEGER NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    text            TEXT NOT NULL,
    verify_json     TEXT,
    feedback        TEXT,
    resume_hash     TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    UNIQUE (application_id, version)
);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    db_path = db_path or config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create the tables if they don't exist. Safe to call on every start-up."""
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
    conn.close()


# --- Applications ----------------------------------------------------------

# Columns the app may set after creating an application.
APPLICATION_FIELDS = {
    "url", "company", "title", "posting_text", "user_notes", "parsed_json", "match_json",
    "status", "approved_at", "submitted_at", "sent_version", "notes",
}
JSON_FIELDS = ("parsed_json", "match_json", "notes")
TRACKING_PARAMS = ("utm_", "gh_src", "jr_", "ref", "source", "src", "trk")


def normalize_url(url: str | None) -> str | None:
    """Canonical form for spotting the same posting twice: no fragment, tracking
    parameters, trailing slash or letter-case differences in the host."""
    if not url or not url.strip():
        return None
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(TRACKING_PARAMS)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    for field in JSON_FIELDS:
        if field in data and data[field]:
            data[field] = json.loads(data[field])
    return data


def create_application(url: str | None, posting_text: str, user_notes: str = "") -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO applications (url, posting_text, user_notes) VALUES (?, ?, ?)",
            (normalize_url(url), posting_text, user_notes),
        )
        app_id = cur.lastrowid
    conn.close()
    return app_id


def update_application(app_id: int, **fields) -> None:
    unknown = set(fields) - APPLICATION_FIELDS
    if unknown:
        raise ValueError(f"Unknown application fields: {sorted(unknown)}")
    if not fields:
        return
    values = [json.dumps(v) if k in JSON_FIELDS and v is not None else v for k, v in fields.items()]
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with connect() as conn:
        conn.execute(f"UPDATE applications SET {assignments} WHERE id = ?", (*values, app_id))
    conn.close()


def get_application(app_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def find_by_url(url: str | None) -> dict | None:
    """The most recent application for this posting URL, if any."""
    key = normalize_url(url)
    if key is None:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE url = ? ORDER BY id DESC LIMIT 1", (key,)
        ).fetchone()
    conn.close()
    return _row_to_dict(row)


# --- Draft versions --------------------------------------------------------


def add_draft(app_id: int, text: str, resume_hash: str, feedback: str | None = None,
              verify: dict | None = None) -> int:
    """Save a new draft version and return its number (1, 2, ...)."""
    with connect() as conn:
        current = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM drafts WHERE application_id = ?", (app_id,)
        ).fetchone()[0]
        version = current + 1
        conn.execute(
            "INSERT INTO drafts (application_id, version, text, verify_json, feedback, resume_hash)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (app_id, version, text, json.dumps(verify) if verify else None, feedback, resume_hash),
        )
    conn.close()
    return version


def list_drafts(app_id: int) -> list[dict]:
    """All versions, newest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM drafts WHERE application_id = ? ORDER BY version DESC", (app_id,)
        ).fetchall()
    conn.close()
    drafts = [dict(r) for r in rows]
    for d in drafts:
        d["verify_json"] = json.loads(d["verify_json"]) if d["verify_json"] else None
    return drafts


def latest_draft(app_id: int) -> dict | None:
    drafts = list_drafts(app_id)
    return drafts[0] if drafts else None


def set_verify(app_id: int, version: int, verify: dict) -> None:
    """Store the check results for a version that was saved before it could be checked."""
    with connect() as conn:
        conn.execute(
            "UPDATE drafts SET verify_json = ? WHERE application_id = ? AND version = ?",
            (json.dumps(verify), app_id, version),
        )
    conn.close()


# --- Approval ----------------------------------------------------------------


def _now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def approve(app_id: int, version: int) -> None:
    """Only the Approve button calls this (spec: Human approval & guardrails)."""
    update_application(app_id, status="approved", approved_at=_now(), sent_version=version)


def return_to_draft(app_id: int) -> bool:
    """Any change to an approved letter makes it a draft again. Returns True if it was approved."""
    app = get_application(app_id)
    if app and app["status"] == "approved":
        update_application(app_id, status="draft", approved_at=None, sent_version=None)
        return True
    return False


def save_version(app_id: int, text: str, resume_hash: str, feedback: str | None = None,
                 verify: dict | None = None) -> int:
    """Save a new letter version; an approved letter goes back to draft."""
    version = add_draft(app_id, text, resume_hash, feedback=feedback, verify=verify)
    return_to_draft(app_id)
    return version
