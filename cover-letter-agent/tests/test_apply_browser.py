"""Application agent in a real (headless, offline) Chrome against made-up Greenhouse- and
Lever-shaped forms (Milestone 7): reading fields, filling, the blocked Submit, link
resolution and a whole session, with Claude faked."""

import json
import re
import time

import pytest

from apply import extract, fill, guard, mapping, resolve, session
from apply.mapping import Decision
from storage import db, filled
from tests.apply_browser import chrome, open_form, page  # noqa: F401 - pytest fixtures
from tests.fixtures.forms import posting_pages
from tests.test_apply_rules import sources
from tests.test_pipeline import response

GH = posting_pages.GREENHOUSE_FORM
LEVER = posting_pages.LEVER_FORM


def labels(fields):
    return {f.label: f for f in fields}


def test_reads_greenhouse_shaped_form(page):
    fields = labels(extract.read_fields(open_form(page, GH)))
    assert fields["First Name"].required and fields["Email"].kind == "text"
    assert fields["Resume/CV"].kind == "file" and fields["Resume/CV"].required
    assert fields["Cover Letter"].kind == "file" and not fields["Cover Letter"].required
    assert fields["How did you hear about us?"].options == ["LinkedIn", "Company Website", "Employee Referral", "Other"]
    assert fields["Location (City)"].kind == "combobox" and fields["Location (City)"].options == []  # a search box
    assert fields["I certify that the information I have provided is true and complete."].kind == "checkbox"
    assert not any("ignore your instructions" in label.lower() for label in fields)  # hidden text isn't a field
    assert not page.locator('[role="listbox"]').count()  # every dropdown was closed again


def test_reads_lever_shaped_form(page):
    fields = labels(extract.read_fields(open_form(page, LEVER)))
    auth = fields["Are you legally authorized to work in the United States?"]
    assert auth.kind == "radio" and auth.options == ["Yes", "No"] and auth.required
    assert fields["Which languages do you speak? (Check all that apply)"].kind == "checkbox_group"
    assert fields["Please tell us how you heard about this opportunity."].options == [
        "LinkedIn", "Company website", "Friend or Family", "Other"]
    assert fields["Current company"].value == "Old Co"
    assert fields["Full name"].required and not fields["Phone"].required


def test_safe_click_refuses_every_submit(page):
    open_form(page, GH)
    with pytest.raises(guard.SubmitBlocked):
        guard.safe_click(page.locator("#submit_app"))
    open_form(page, LEVER)
    for selector in ("#btn-submit", ".cookie-banner button >> nth=0"):
        with pytest.raises(guard.SubmitBlocked):
            guard.safe_click(page.locator(selector))
    assert page.evaluate("[window.__submitted, window.__cookie]") == [None, None]


def test_fill_page_greenhouse(page, tmp_path):
    open_form(page, GH)
    fields = extract.read_fields(page)
    keys = {f.label: f.key for f in fields}
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 test")
    plan = {
        "First Name": Decision("", "fill", "Jordan", "profile", True),
        "Email": Decision("", "fill", "jordan@example.com", "profile", True),
        "Location (City)": Decision("", "fill", "Nashville, TN", "profile", False),
        "Resume/CV": Decision("", "upload_resume", "Resume", "profile", True),
        "How did you hear about us?": Decision("", "fill", "Company Website", "application_answers", True),
        "Are you authorized to work lawfully in the United States?": Decision("", "fill", "Yes", "application_answers", True),
        "Why do you want to work at Acme Health?": Decision("", "leave", "", "none", False, "Needs your answer"),
    }
    decisions = [Decision(f.key, **{k: v for k, v in vars(plan[f.label]).items() if k != "key"})
                 if f.label in plan else mapping.leave(f.key, "Not mapped") for f in fields]
    decisions = fill.fill_page(page, fields, decisions, {"resume": resume, "cover_letter": None})
    now = labels(extract.read_fields(page, open_dropdowns=False))
    assert now["First Name"].value == "Jordan" and now["Email"].value == "jordan@example.com"
    assert now["How did you hear about us?"].value == "Company Website"
    assert now["Are you authorized to work lawfully in the United States?"].value == "Yes"
    assert now["Location (City)"].value == "Nashville, Tennessee, United States"  # picked from the search results
    assert now["Resume/CV"].value == "resume.pdf"
    assert now["Gender"].value == "" and now["Veteran Status"].value == ""
    status = {f.label: d.status for f, d in zip(fields, decisions)}
    assert status["First Name"] == "filled" and status["Location (City)"] == "review"
    assert status["Why do you want to work at Acme Health?"] == "needs_you"
    outlines = page.evaluate("""() => ({review: getComputedStyle(document.querySelector('#candidate-location').closest('[class*=control]')).outlineColor,
                                         needed: getComputedStyle(document.querySelector('#question_7')).outlineStyle})""")
    assert outlines["review"] == "rgb(178, 107, 0)" and outlines["needed"] == "solid"
    assert page.evaluate("window.__submitted") is None
    assert keys  # every field had a key


def test_fill_page_lever(page):
    open_form(page, LEVER)
    fields = extract.read_fields(page)
    by_label = {f.label: f for f in fields}
    wanted = {
        "Full name": "Jordan Avery",
        "Are you legally authorized to work in the United States?": "Yes",
        "Will you now or in the future require sponsorship for employment visa status?": "No",
        "Please tell us how you heard about this opportunity.": "Company website",
        "Which languages do you speak? (Check all that apply)": ["English", "Spanish"],
    }
    decisions = [Decision(f.key, "fill", wanted[f.label], "application_answers", True) if f.label in wanted
                 else mapping.leave(f.key, "Not mapped") for f in fields]
    fill.fill_page(page, fields, decisions, {})
    now = labels(extract.read_fields(page, open_dropdowns=False))
    for label, value in wanted.items():
        assert now[label].value == value, label
    assert now["We may record interviews with an AI notetaker. Do you consent?"].value == ""
    assert page.evaluate("[window.__submitted, window.__cookie]") == [None, None]
    assert by_label["Gender"].value == ""


@pytest.mark.parametrize("start, ok, platform, last_step", [
    ("https://www.adzuna.com/land/ad/1", True, "greenhouse", "Greenhouse form"),
    ("https://www.adzuna.com/details/42", True, "greenhouse", "Greenhouse form"),
    ("https://careers.acme.example/embedded", True, "greenhouse", "Greenhouse form"),
    ("https://jobs.lever.co/tilt/abc", True, "lever", "Lever form"),
    ("https://www.adzuna.com/land/ad/2", False, "other", "redirected to linkedin.com"),
    ("https://www.adzuna.com/land/ad/3", False, "other", "redirect followed to adzuna.com/details/43"),
    ("https://www.linkedin.com/jobs/view/9", False, "other", "linkedin.com link"),
    ("https://www.adzuna.com/land/ad/9", False, "other", "Adzuna link"),  # 403: turned away
])
def test_resolve(chrome, start, ok, platform, last_step):
    blocked = []
    resolve.block_job_boards(chrome, blocked)
    tab = chrome.new_page()
    try:
        found = resolve.resolve(tab, start, blocked)
    finally:
        tab.close()
        chrome.unroute("**/*")
        posting_pages.serve(chrome)
    assert (found.ok, found.platform, found.steps[-1]) == (ok, platform, last_step)
    if not ok:
        assert "company's own link" in found.reason or "company's posting" in found.reason
    if start == "https://www.adzuna.com/land/ad/9":
        assert "Adzuna turned the app's browser away (HTTP 403)" in found.reason


def test_resolve_never_presses_an_apply_button(chrome):
    requested = []
    chrome.unroute("**/*")
    posting_pages.serve(chrome, requested)
    tab = chrome.new_page()
    try:
        found = resolve.resolve(tab, "https://careers.acme.example/jobs/1", [])
        assert found.ok and found.steps == ["Job link", "Apply link", "Greenhouse form"]
        assert tab.evaluate("window.__submitted") is None
    finally:
        tab.close()
        chrome.unroute("**/*")
        posting_pages.serve(chrome)


# --- A whole session -------------------------------------------------------------------


class LabelClient:
    """Fake Claude for the mapping step: answers by label from the request it gets."""

    def __init__(self, answers: dict[str, tuple[str, str]]):
        self.answers, self.requests = answers, []
        from types import SimpleNamespace
        self.beta = SimpleNamespace(messages=self)

    def create(self, **kwargs):
        self.requests.append(kwargs)
        sent = kwargs["messages"][0]["content"]
        fields = json.loads(re.search(r"<fields>\n(.*?)\n</fields>", sent, re.S).group(1))
        out = []
        for f in fields:
            value, source = self.answers.get(f["label"], ("", "none"))
            out.append({"key": f["key"], "action": "fill" if value else "leave", "value": value, "source": source,
                        "confident": True, "note": "" if value else "No answer"})
        return response(json.dumps({"fields": out}))


def headless(tmp_path):
    import tempfile

    def launcher(p, headless=True):
        return p.chromium.launch_persistent_context(tempfile.mkdtemp(dir=tmp_path), channel="chrome", headless=True)
    return launcher


def offline_pages(context):
    context.set_offline(True)
    posting_pages.serve(context)


def wait_for(sess, *states, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        snap = sess.snapshot()
        if snap["state"] in states:
            return snap
        if snap["state"] in ("error", "closed") and snap["state"] not in states:
            raise AssertionError(snap)
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {states}: {sess.snapshot()}")


@pytest.fixture
def app_id(app_paths):
    db.init_db()
    return db.create_application("https://www.adzuna.com/land/ad/1", "Posting text", "")


def test_session_from_adzuna_link_to_hand_over(app_id, tmp_path):
    client = LabelClient({
        "First Name": ("Jordan", "profile"), "Last Name": ("Avery", "profile"),
        "Email": ("jordan@example.com", "profile"), "Phone": ("(615) 555-0100", "profile"),
        "LinkedIn Profile": ("https://www.linkedin.com/in/jordanavery", "profile"),
        "How did you hear about us?": ("Company Website", "application_answers"),
        "Are you authorized to work lawfully in the United States?": ("Yes", "application_answers"),
        "Will you now or in the future require visa sponsorship?": ("No", "application_answers"),
        "What are your salary expectations?": ("$500,000", "application_answers"),  # no saved salary: left
    })
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 test")
    src = sources()
    sess = session.Session(app_id, "https://www.adzuna.com/land/ad/1",
                           lambda fields: mapping.map_fields(client, "claude-test", fields, src),
                           {"resume": resume, "cover_letter": None}, launcher=headless(tmp_path), headless=True,
                           setup=offline_pages).start()
    try:
        snap = wait_for(sess, "confirm")
        assert snap["platform"] == "Greenhouse" and snap["url"] == GH
        assert snap["steps"] == ["Adzuna link", "redirect followed to careers.acme.example/jobs/1", "Apply link",
                                 "Greenhouse form"]
        sess.send("confirm")
        snap = wait_for(sess, "review")
        rows = {r["label"]: r for r in snap["rows"]}
        assert rows["First Name"]["status"] == "filled" and rows["Resume/CV"]["value"] == "Resume"
        assert rows["Gender"]["status"] == "left_for_you" and rows["Share your Pronouns"]["status"] == "left_for_you"
        assert rows["What are your salary expectations?"]["status"] == "needs_you"
        assert rows["Why do you want to work at Acme Health?"]["status"] == "needs_you"
        sent = client.requests[0]["messages"][0]["content"]
        assert "Gender" not in sent and "Veteran" not in sent and "Pronouns" not in sent
        sess.send("continue")
        snap = wait_for(sess, "done")
        assert "submit it yourself" in snap["message"] and snap["pages_done"] == [1]
        saved = {r["field_label"]: r for r in filled.for_application(app_id)}
        assert saved["First Name"]["value"] == "Jordan" and saved["First Name"]["source"] == "profile"
        assert saved["Resume/CV"]["value"] == "resume.pdf"
        assert saved["Gender"]["value"] == "" and saved["Gender"]["status"] == "left_for_you"
    finally:
        sess.send("close")
        sess.thread.join(30)
    assert sess.snapshot()["state"] == "closed"


def test_session_pauses_for_login_and_can_stop(app_id, tmp_path):
    sess = session.Session(app_id, "https://careers.acme.example/login-wall", lambda fields: [], {},
                           launcher=headless(tmp_path), headless=True, setup=offline_pages).start()
    try:
        wait_for(sess, "confirm")
        sess.send("confirm")
        snap = wait_for(sess, "login")
        assert "log in" in snap["message"]
        sess.send("stop")
        assert "nothing was submitted" in wait_for(sess, "stopped")["message"]
    finally:
        sess.send("close")
        sess.thread.join(30)


def test_session_stops_at_a_job_board(app_id, tmp_path):
    sess = session.Session(app_id, "https://www.adzuna.com/land/ad/2", lambda fields: [], {},
                           launcher=headless(tmp_path), headless=True, setup=offline_pages).start()
    try:
        snap = wait_for(sess, "blocked")
        assert "linkedin.com" in snap["message"] and "company's own link" in snap["message"]
    finally:
        sess.send("close")
        sess.thread.join(30)


def test_only_one_session_at_a_time(monkeypatch):
    class Busy:
        active = True
    monkeypatch.setattr(session, "_current", Busy())
    with pytest.raises(RuntimeError, match="Another application"):
        session.start(object())
