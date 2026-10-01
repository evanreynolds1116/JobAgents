import sqlite3

import pytest

from storage import db

APPLICATION_COLUMNS = {
    "id", "url", "company", "title", "posting_text", "user_notes", "parsed_json",
    "match_json", "status", "created_at", "approved_at", "submitted_at",
    "sent_version", "notes",
}
DRAFT_COLUMNS = {
    "id", "application_id", "version", "text", "verify_json", "feedback",
    "resume_hash", "created_at",
}


def columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


@pytest.fixture
def conn(app_paths):
    db.init_db()
    db.init_db()  # second call must be harmless
    conn = db.connect()
    yield conn
    conn.close()


def test_schema_matches_spec(conn):
    assert columns(conn, "applications") == APPLICATION_COLUMNS
    assert columns(conn, "drafts") == DRAFT_COLUMNS


def test_new_application_defaults_to_draft(conn):
    conn.execute("INSERT INTO applications (url) VALUES ('https://example.com/job')")
    row = conn.execute("SELECT status, created_at, notes FROM applications").fetchone()
    assert row["status"] == "draft"
    assert row["created_at"]
    assert row["notes"] == "[]"


def test_unknown_status_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO applications (status) VALUES ('sent')")


def test_draft_needs_existing_application(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO drafts (application_id, version, text) VALUES (999, 1, 'x')")


def test_draft_versions_unique_per_application(conn):
    app_id = conn.execute("INSERT INTO applications (company) VALUES ('Acme')").lastrowid
    conn.execute("INSERT INTO drafts (application_id, version, text) VALUES (?, 1, 'v1')", (app_id,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO drafts (application_id, version, text) VALUES (?, 1, 'dup')", (app_id,))
