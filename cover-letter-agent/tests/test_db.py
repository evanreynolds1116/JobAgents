import sqlite3

import pytest

from storage import db

APPLICATION_COLUMNS = {
    "id", "url", "company", "title", "posting_text", "user_notes", "parsed_json",
    "match_json", "status", "created_at", "approved_at", "submitted_at",
    "sent_version", "notes", "job_id",  # job_id: the shortlisted job it was started from (Milestone 12)
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


# --- Queries -----------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("Boards.Greenhouse.io/acme/jobs/123/?gh_src=abc&utm_source=x#apply", "https://boards.greenhouse.io/acme/jobs/123"),
    ("https://jobs.example.com/view?id=42&utm_campaign=z", "https://jobs.example.com/view?id=42"),
    ("https://jobs.ashbyhq.com/acme/123/application?jr_id=6abd", "https://jobs.ashbyhq.com/acme/123/application"),
    ("  ", None),
    (None, None),
])
def test_normalize_url(raw, expected):
    assert db.normalize_url(raw) == expected


def test_application_round_trip(conn):
    app_id = db.create_application("https://acme.example/jobs/1/", "Posting text", "My notes")
    db.update_application(app_id, parsed_json={"company": "Acme", "must_have": ["SQL"]},
                          company="Acme", title="Analyst")
    app = db.get_application(app_id)
    assert app["url"] == "https://acme.example/jobs/1"
    assert app["parsed_json"] == {"company": "Acme", "must_have": ["SQL"]}
    assert app["match_json"] is None and app["notes"] == []
    assert db.find_by_url("acme.example/jobs/1#top")["id"] == app_id
    assert db.find_by_url("https://acme.example/jobs/2") is None
    db.update_application(app_id, match_json=None)
    with pytest.raises(ValueError):
        db.update_application(app_id, id=5)


def test_draft_versions_count_up(conn):
    app_id = db.create_application(None, "Posting", "")
    assert db.add_draft(app_id, "First", "h1") == 1
    assert db.add_draft(app_id, "Second", "h1", feedback="Shorter") == 2
    drafts = db.list_drafts(app_id)
    assert [d["version"] for d in drafts] == [2, 1]
    assert drafts[0]["feedback"] == "Shorter" and drafts[1]["verify_json"] is None


# --- Approval ------------------------------------------------------------------


def test_approve_then_edit_returns_to_draft(conn):
    app_id = db.create_application(None, "Posting", "")
    db.add_draft(app_id, "v1", "h")
    db.approve(app_id, 1)
    app = db.get_application(app_id)
    assert app["status"] == "approved" and app["sent_version"] == 1 and app["approved_at"]

    assert db.save_version(app_id, "v2 edited", "h", feedback="Edited by hand") == 2
    app = db.get_application(app_id)
    assert app["status"] == "draft" and app["approved_at"] is None and app["sent_version"] is None


def test_new_version_of_a_draft_stays_draft(conn):
    app_id = db.create_application(None, "Posting", "")
    db.save_version(app_id, "v1", "h")
    assert not db.return_to_draft(app_id)
    assert db.get_application(app_id)["status"] == "draft"


def test_set_verify_on_existing_version(conn):
    app_id = db.create_application(None, "Posting", "")
    db.add_draft(app_id, "v1", "h")
    db.set_verify(app_id, 1, {"claims": [], "style_flags": [], "lint": []})
    assert db.latest_draft(app_id)["verify_json"] == {"claims": [], "style_flags": [], "lint": []}


def test_export_refused_for_drafts(conn):
    from export.docx import NotApproved, can_export, require_approved

    app_id = db.create_application(None, "Posting", "")
    db.add_draft(app_id, "v1", "h")
    with pytest.raises(NotApproved):
        require_approved(db.get_application(app_id))
    db.approve(app_id, 1)
    assert can_export(db.get_application(app_id))
    db.save_version(app_id, "v2", "h")
    assert not can_export(db.get_application(app_id))
