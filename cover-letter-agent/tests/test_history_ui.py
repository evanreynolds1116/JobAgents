"""Applications list, application detail, and export from the review screen."""

from datetime import datetime, timedelta

import pytest
from streamlit.testing.v1 import AppTest

import config
from export import docx as exporter
from storage import db, resume
from storage import profile as profile_store
from ui import dates, nav

POSTING = "Marketing Coordinator\nHarpeth Outdoor Co.\n\nYou'll run our newsletter and paddle festivals."
CLEAN = {"claims": [], "style_flags": [], "lint": []}
FLAGGED = {"claims": [{"claim": "x", "supported": False, "source": "none", "evidence": "", "reason": "r"}],
           "style_flags": [], "lint": []}


@pytest.fixture
def went(app_paths, monkeypatch):
    db.init_db()
    resume.save_text("# Jordan Avery\n\nMarketing coordinator.")
    profile_store.save(profile_store.Profile(name="Jordan Avery", email="jordan@example.com"))
    log = []
    monkeypatch.setattr(nav, "go", lambda key, **params: log.append((key, params)))
    return log


def make(company, title, status="draft", verify=CLEAN, versions=1, notes=None) -> int:
    app_id = db.create_application(f"https://{company.lower().replace(' ', '')}.example/job", POSTING, "")
    db.update_application(app_id, company=company, title=title,
                          parsed_json={"company": company, "title": title, "location": "Franklin, TN"})
    for v in range(1, versions + 1):
        db.add_draft(app_id, f"Dear Priya,\n\nVersion {v} of the letter.\n\nThanks,\nJordan Avery", "h",
                     verify=verify)
    if status in ("approved", "submitted", "archived"):
        db.approve(app_id, 1)
    if status == "submitted":
        db.mark_submitted(app_id)
    if status == "archived":
        db.archive(app_id)
    for note in notes or []:
        db.add_note(app_id, note)
    return app_id


def page(fn_name, app_id=None):
    # from_function can't take arguments, so each page gets its own tiny script.
    scripts = {
        "applications": "def s():\n    from ui import applications\n    applications.applications_page()\n",
        "detail": "def s():\n    from ui import detail\n    detail.detail_page()\n",
        "review": "def s():\n    from ui import review\n    review.review_page()\n",
    }
    at = AppTest.from_string(scripts[fn_name] + "s()\n", default_timeout=30)
    if app_id is not None:
        at.query_params["app"] = str(app_id)
    at.run()
    assert not at.exception, at.exception
    return at


def click(at, label, nth=0):
    [b for b in at.button if b.label == label][nth].click().run()
    assert not at.exception, at.exception


def text(at) -> str:
    return "\n".join(m.value for m in at.markdown)


# --- Applications list -----------------------------------------------------------


def test_empty_list_points_to_new_letter(went):
    at = page("applications")
    assert "No applications yet" in text(at)
    click(at, "New cover letter")
    assert went == [("new_letter", {})]


def test_list_shows_status_letter_and_next_step(went):
    make("Brightline Health", "Content Marketing Specialist", verify=FLAGGED)
    make("Northwind Outfitters", "Marketing Coordinator", status="approved")
    make("Fieldhouse Media", "Social Media Manager", status="submitted", versions=3)
    make("Copperleaf Foods", "Marketing Associate", status="archived")
    at = page("applications")
    page_text = text(at)
    assert "4 applications · 1 submitted" in page_text
    for expected in ("Draft", "Draft v1 · 1 flag", "Letter approved", "Approved v1",
                     f"Submitted {dates.day(datetime.now().isoformat())}", "Archived"):
        assert expected in page_text, expected
    labels = [b.label for b in at.button if b.key and b.key.startswith("ap_action_")]
    assert sorted(labels) == ["Open details", "Open letter", "Restore", "Review draft"]
    assert at.segmented_control(key="ap_filter").options == ["All (4)", "In progress (2)", "Submitted (1)", "Archived (1)"]


def test_search_and_filters(went):
    make("Brightline Health", "Content Marketing Specialist")
    make("Fieldhouse Media", "Social Media Manager", status="submitted")
    at = page("applications")
    at.text_input(key="ap_search").input("fieldhouse").run()
    titles = [b.label for b in at.button if b.key and b.key.startswith("ap_open_")]
    assert titles == ["Social Media Manager"]
    at.text_input(key="ap_search").input("MARKETING").run()  # title search, any case
    assert [b.label for b in at.button if b.key and b.key.startswith("ap_open_")] == ["Content Marketing Specialist"]
    at.text_input(key="ap_search").input("").run()
    at.segmented_control(key="ap_filter").set_value("Submitted").run()
    assert [b.label for b in at.button if b.key and b.key.startswith("ap_open_")] == ["Social Media Manager"]


def test_row_buttons(went):
    archived = make("Copperleaf Foods", "Marketing Associate", status="archived")
    draft = make("Brightline Health", "Content Marketing Specialist")
    at = page("applications")
    click(at, "Content Marketing Specialist")
    click(at, "Review draft")
    assert went == [("detail", {"app": draft}), ("review", {"app": draft})]
    click(at, "Restore")
    assert db.get_application(archived)["status"] == "approved"  # back to where it was


# --- Detail page ---------------------------------------------------------------------


def test_detail_shows_dates_posting_and_the_letter_you_approved(went):
    app_id = make("Fieldhouse Media", "Social Media Manager", status="submitted", versions=3,
                  notes=["Recruiter call, 15 minutes. Second interview next week."])
    at = page("detail", app_id)
    assert at.title[0].value == "Social Media Manager"
    page_text = text(at)
    assert "Original posting link" in page_text
    assert "You submitted" in [c.value for c in at.caption]
    assert "Version 1" in [c.value for c in at.caption]
    assert at.tabs[1].label == "Cover letter sent (v1)"
    assert "Version 1 of the letter" in page_text and "Version 3 of the letter" not in page_text
    assert "You'll run our newsletter and paddle festivals." in page_text
    assert "Recruiter call, 15 minutes. Second interview next week." in page_text


def test_notes_log(went):
    app_id = make("Fieldhouse Media", "Social Media Manager")
    at = page("detail", app_id)
    at.text_area(key=f"dt_note_{app_id}").input("Phone screen booked for Friday 2pm.")
    click(at, "Save note")
    notes = db.get_application(app_id)["notes"]
    assert [n["text"] for n in notes] == ["Phone screen booked for Friday 2pm."]
    assert datetime.fromisoformat(notes[0]["date"]) > datetime.now() - timedelta(minutes=1)
    assert "Phone screen booked for Friday 2pm." in text(at)


def test_mark_submitted_archive_and_restore(went):
    app_id = make("Northwind Outfitters", "Marketing Coordinator", status="approved")
    at = page("detail", app_id)
    click(at, "Mark as submitted")
    app = db.get_application(app_id)
    assert app["status"] == "submitted" and app["submitted_at"] and app["sent_version"] == 1
    click(at, "Archive")
    assert db.get_application(app_id)["status"] == "archived"
    click(at, "Restore")
    assert db.get_application(app_id)["status"] == "submitted"


def test_detail_without_application(went):
    assert "No application is open" in page("detail", 42).info[0].value


# --- Export from the review screen ------------------------------------------------


def test_export_docx_from_review(went):
    app_id = make("Northwind Outfitters", "Marketing Coordinator", status="approved", versions=2)
    at = page("review", app_id)
    click(at, "Export .docx")
    path = config.OUTPUT_DIR / "Northwind Outfitters - Marketing Coordinator - Cover Letter.docx"
    assert path.exists()
    assert any(d.label == f"Download {path.name}" for d in at.get("download_button"))


def test_export_pdf_falls_back_to_docx_message(went, monkeypatch):
    app_id = make("Northwind Outfitters", "Marketing Coordinator", status="approved")

    def no_pdf(*args, **kwargs):
        raise exporter.PdfUnavailable("Couldn't make the PDF. It needs Microsoft Word or LibreOffice installed.")

    monkeypatch.setattr(exporter, "export_pdf", no_pdf)
    at = page("review", app_id)
    click(at, "Export PDF")
    assert "Microsoft Word or LibreOffice" in at.warning[0].value
    assert (config.OUTPUT_DIR / "Northwind Outfitters - Marketing Coordinator - Cover Letter.docx").exists()
