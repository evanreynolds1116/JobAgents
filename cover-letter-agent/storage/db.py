"""SQLite schema and connection for data/app.db.

Tables follow the spec's Data & storage section. Phase 2 and 3 tables
(saved_answers, filled_answers, saved_searches, jobs) are added in their own milestones.
"""

import sqlite3
from pathlib import Path

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
