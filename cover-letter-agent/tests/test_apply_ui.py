"""Filling application screen, the Fill application buttons and the recorded answers
(Milestone 7), with the browser session faked."""

import config
from apply import session, start
from storage import filled
from tests.test_history_ui import click, make, page, text, went  # noqa: F401 - went is a fixture
from ui.apply import summary


def apply_page(app_id=None):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string("from ui import apply\napply.apply_page()\n", default_timeout=30)
    if app_id is not None:
        at.query_params["app"] = str(app_id)
    at.run()
    assert not at.exception, at.exception
    return at


class FakeSession:
    def __init__(self, app_id, state="review", **extra):
        self.app_id, self.active, self.sent = app_id, True, []
        self.snap = {"state": state, "message": "Paused on page 1.", "url": "https://job-boards.greenhouse.io/x/1",
                     "platform": "Greenhouse", "steps": ["Adzuna link", "Apply link", "Greenhouse form"], "page": 1,
                     "pages_done": [], "error": "",
                     "rows": [{"label": "First Name", "kind": "text", "required": True, "value": "Jordan",
                               "source": "profile", "status": "filled", "note": ""},
                              {"label": "Gender", "kind": "combobox", "required": False, "value": "",
                               "source": "none", "status": "left_for_you", "note": "The agent never answers these"},
                              {"label": "Location", "kind": "combobox", "required": True, "value": "Nashville, TN",
                               "source": "profile", "status": "review", "note": ""}]}
        self.snap.update(extra)

    def snapshot(self):
        return dict(self.snap)

    def send(self, command):
        self.sent.append(command)


def key(monkeypatch_env=None):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n")


def test_summary():
    rows = FakeSession(1).snap["rows"]
    assert summary(rows) == "1 filled · 1 to review · 1 left for you"


def test_without_an_approved_letter_fills_without_one(went, monkeypatch):
    key()
    monkeypatch.setattr(session, "_current", None)
    draft = make("Acme", "Engineer")
    at = apply_page(draft)
    assert not at.warning and not next(b for b in at.button if b.label == "Open the form").disabled
    assert any("No approved cover letter: the form is filled without one" in c.value for c in at.caption)
    assert "It never clicks Submit." in text(at)


def test_needs_a_job_link(went, monkeypatch):
    key()
    monkeypatch.setattr(session, "_current", None)
    from storage import db
    app_id = db.create_application(None, "Posting text", "")
    at = apply_page(app_id)
    assert "no job link" in at.warning[0].value
    assert next(b for b in at.button if b.label == "Open the form").disabled


def test_open_the_form_starts_a_session(went, monkeypatch):
    key()
    monkeypatch.setattr(session, "_current", None)
    app_id = make("Acme", "Engineer", status="approved")
    started = []
    monkeypatch.setattr(start, "prepare", lambda i: FakeSession(i, state="finding"))
    monkeypatch.setattr(session, "start", lambda s: (started.append(s), setattr(session, "_current", s))[1])
    at = apply_page(app_id)
    assert not next(b for b in at.button if b.label == "Open the form").disabled
    click(at, "Open the form")
    assert started and started[0].app_id == app_id


def test_live_review(went, monkeypatch):
    key()
    app_id = make("Acme", "Engineer", status="approved")
    fake = FakeSession(app_id)
    monkeypatch.setattr(session, "_current", fake)
    at = apply_page(app_id)
    assert "Adzuna link → Apply link → Greenhouse form" in text(at)
    assert "1 filled · 1 to review · 1 left for you" in text(at)
    table = at.dataframe[0].value
    assert list(table["Status"]) == ["Filled", "Left for you", "Review"]
    assert list(table["Field"]) == ["First Name *", "Gender", "Location *"]
    assert table["What the agent entered"][1] == "The agent never answers these"
    click(at, "Continue from page 1")
    assert fake.sent == ["continue"]
    click(at, "Stop filling")
    assert fake.sent == ["continue", "stop"]


def test_live_states(went, monkeypatch):
    key()
    app_id = make("Acme", "Engineer", status="approved")
    for state, button, command in (("confirm", "Confirm form", "confirm"), ("login", "Resume", "resume"),
                                   ("done", "Close browser", "close")):
        fake = FakeSession(app_id, state=state, rows=[])
        monkeypatch.setattr(session, "_current", fake)
        at = apply_page(app_id)
        click(at, button)
        assert fake.sent == [command], state
    fake = FakeSession(app_id, state="blocked", rows=[], message="This link leads to linkedin.com.")
    monkeypatch.setattr(session, "_current", fake)
    at = apply_page(app_id)
    assert "linkedin.com" in at.warning[0].value
    at.text_input(key="ap_new_url").input("job-boards.greenhouse.io/acme/jobs/1").run()
    click(at, "Use this link")
    from storage import db
    assert db.get_application(app_id)["url"] == "https://job-boards.greenhouse.io/acme/jobs/1"
    assert fake.sent == ["close"]


def test_review_and_detail_buttons(went):
    key()
    draft = make("Acme", "Engineer")
    approved = make("Tilt", "Backend Engineer", status="approved")
    at = page("review", draft)
    assert next(b for b in at.button if b.label == "Fill application").disabled
    at = page("review", approved)
    click(at, "Fill application")
    assert went[-1] == ("apply", {"app": approved})
    at = page("detail", approved)
    click(at, "Fill application")
    assert went[-1] == ("apply", {"app": approved})


def test_detail_shows_recorded_answers(went):
    key()
    app_id = make("Acme", "Engineer", status="approved")
    at = page("detail", app_id)
    assert "No form answers yet." in text(at)
    filled.save_page(app_id, 1, [
        {"label": "First Name", "value": "Jordan", "source": "profile", "status": "filled"},
        {"label": "Languages", "value": ["English", "Spanish"], "source": "you", "status": "you"},
        {"label": "Gender", "value": "", "source": "none", "status": "left_for_you"}])
    at = page("detail", app_id)
    table = at.dataframe[0].value
    assert list(table["Field"]) == ["First Name", "Languages", "Gender"]
    assert list(table["Value"]) == ["Jordan", "English, Spanish", ""]
    assert list(table["Source"]) == ["Your profile", "You", ""]
    assert list(table["Status"]) == ["Filled", "Your edit", "Left for you"]


# --- Milestone 8 ------------------------------------------------------------------------


def test_needs_letter_pause(went, monkeypatch):
    key()
    app_id = make("Acme", "Engineer")
    fake = FakeSession(app_id, state="needs_letter", rows=[], message="This form requires a cover letter.")
    monkeypatch.setattr(session, "_current", fake)
    at = apply_page(app_id)
    click(at, "Fill without it")
    assert fake.sent == ["skip_letter"]
    at = apply_page(app_id)
    click(at, "Draft a cover letter")
    assert fake.sent[-1] == "close" and went[-1] == ("new_letter", {"draft": app_id})


def test_offer_to_save_typed_answers(went, monkeypatch):
    from storage import answers

    key()
    app_id = make("Acme", "Engineer")
    fake = FakeSession(app_id, state="done", rows=[], message="All filled.",
                       offers=[{"label": "When could you start?", "value": "Two weeks after an offer"},
                               {"label": "Preferred working hours?", "value": "Central time"}])
    monkeypatch.setattr(session, "_current", fake)
    at = apply_page(app_id)
    assert "You typed an answer for **When could you start?**" in text(at)
    click(at, "Save answer")
    assert [(a["question"], a["answer"]) for a in answers.list_answers()] == [
        ("When could you start?", "Two weeks after an offer")]
    assert "When could you start?" not in text(at)
    click(at, "Not now")
    assert "Preferred working hours?" not in text(at) and answers.count() == 1


def test_detail_offers_fill_without_letter(went):
    key()
    draft = make("Acme", "Engineer")
    at = page("detail", draft)
    click(at, "Fill without cover letter")
    assert went[-1] == ("apply", {"app": draft})


def test_multi_page_progress(went, monkeypatch):
    from ui.apply import progress

    key()
    app_id = make("Acme", "Engineer")
    fake = FakeSession(app_id, page=2, pages_done=[1], titles={"1": "My Information", "2": "Application Questions"})
    monkeypatch.setattr(session, "_current", fake)
    at = apply_page(app_id)
    assert any("page 2 · Application Questions" in c.value for c in at.caption)
    assert "✓ Page 1 · My Information" in text(at) and "**Now:** Page 2 · Application Questions" in text(at)
    assert progress({"page": 1, "titles": {}, "pages_done": []}) == ""
