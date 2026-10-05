"""Milestone 9 (stretch): multi-step forms shaped like Workday, page by page: list-opening
dropdowns, search prompts that list options on Enter, split date fields, Save and Continue,
errors that keep the form on the same page, and the final review page handed over."""

import pytest

from apply import extract, fill, mapping, resolve, session
from apply.mapping import Decision
from storage import db, filled
from tests.apply_browser import chrome, open_form, page  # noqa: F401 - pytest fixtures
from tests.fixtures.forms import posting_pages
from tests.test_apply_browser import LabelClient, headless, offline_pages, wait_for
from tests.test_apply_rules import sources

WD = posting_pages.WORKDAY_FORM
JOB = "https://acme.wd5.myworkdayjobs.com/en-US/careers/job/Nashville/Software-Engineer_R1"


def by_label(fields):
    return {f.label: f for f in fields}


def test_resolves_workday_job_to_apply_manually(chrome):
    tab = chrome.new_page()
    try:
        found = resolve.resolve(tab, JOB, [])
    finally:
        tab.close()
    assert found.ok and found.platform == "workday" and found.url == WD
    assert found.steps == ["Workday link", "Apply link", "Apply Manually", "Workday form"]


def test_reads_workday_page(page):
    fields = by_label(extract.read_fields(open_form(page, WD)))
    country = fields["Country"]
    assert country.kind == "listbox" and country.value == "United States of America" and country.required
    assert country.options == ["United States of America", "Canada", "Mexico"]
    assert fields["State"].value == "" and fields["State"].options == ["Tennessee", "Texas", "Utah"]
    assert fields["How Did You Hear About Us?"].kind == "combobox" and fields["How Did You Hear About Us?"].required
    assert fields["Have you previously worked for Acme Health?"].kind == "radio"
    assert not page.locator('[role="listbox"]').count()  # every dropdown was closed again


def test_fills_listboxes_and_search_prompt(page):
    open_form(page, WD)
    fields = extract.read_fields(page)
    wanted = {"State": "Tennessee", "Phone Device Type": "Mobile", "How Did You Hear About Us?": "Company Website"}
    decisions = [Decision(f.key, "fill", wanted[f.label], "application_answers", True) if f.label in wanted
                 else mapping.leave(f.key, "Not mapped") for f in fields]
    fill.fill_page(page, fields, decisions, {})
    now = by_label(extract.read_fields(page, open_dropdowns=False))
    assert now["State"].value == "Tennessee" and now["Phone Device Type"].value == "Mobile"
    assert now["How Did You Hear About Us?"].value == "Company Website"  # typed, Enter, then picked
    assert page.evaluate("[window.__submitted, window.__page]") == [None, 0]  # Enter didn't submit or move on


ANSWERS = {
    "Given Name(s)": ("Jordan", "profile"), "Family Name": ("Avery", "profile"),
    "Address Line 1": ("123 Main St", "application_answers"), "City": ("Nashville", "application_answers"),
    "State": ("Tennessee", "application_answers"), "Postal Code": ("37203", "application_answers"),
    "Email Address": ("jordan@example.com", "profile"), "Phone Device Type": ("Mobile", "profile"),
    "Phone Number": ("(615) 555-0100", "profile"),
    "How Did You Hear About Us?": ("Company Website", "application_answers"),
    "Have you previously worked for Acme Health?": ("No", "resume"),
    "Are you legally authorized to work in the United States?": ("Yes", "application_answers"),
    "Will you now or in the future require sponsorship for employment visa status?": ("No", "application_answers"),
    "Date available to start (Month)": ("11", "application_answers"),
    "Date available to start (Year)": ("2026", "application_answers"),
}


@pytest.fixture
def app_id(app_paths):
    db.init_db()
    return db.create_application(JOB, "Acme Health is hiring a Software Engineer.", "")


def run_session(app_id, tmp_path, answers, drafts=None):
    client = LabelClient(answers)
    src = sources()

    def drafter(fields, decisions):
        from apply import screening
        keys = {f.label: f.key for f in fields}
        return screening.apply_drafts(fields, decisions, {keys[k]: v for k, v in (drafts or {}).items() if k in keys})

    return session.Session(app_id, JOB, lambda fields: mapping.map_fields(client, "claude-test", fields, src),
                           {"resume": None, "cover_letter": None}, launcher=headless(tmp_path), headless=True,
                           setup=offline_pages, drafter=drafter, has_letter=False).start(), client


def test_workday_application_page_by_page_to_the_review_page(app_id, tmp_path):
    sess, client = run_session(app_id, tmp_path, ANSWERS, drafts={
        "Why are you interested in this role at Acme Health?": "I build payment systems at HCA, and Acme's work is close."})
    try:
        wait_for(sess, "confirm")
        sess.send("confirm")
        snap = wait_for(sess, "review")
        assert snap["page"] == 1 and snap["titles"]["1"] == "My Information"
        rows = {r["label"]: r for r in snap["rows"]}
        assert all(rows[label]["status"] in ("filled", "review") for label in ANSWERS if label in rows), rows
        assert rows["Country"]["status"] == "needs_you"  # already set by the form; nothing to change
        sess.send("continue")

        snap = wait_for(sess, "review")
        while snap["page"] != 2:
            snap = wait_for(sess, "review")
        assert snap["titles"]["2"] == "Application Questions"
        rows = {r["label"]: r for r in snap["rows"]}
        assert rows["Date available to start (Month)"]["status"] == "review"  # "11" isn't in your saved answers
        assert rows["Date available to start (Day)"]["status"] == "needs_you"
        assert rows["Why are you interested in this role at Acme Health?"]["source"] == "drafted"
        sess.send("continue")

        snap = wait_for(sess, "review")
        while snap["page"] != 3:
            snap = wait_for(sess, "review")
        rows = {r["label"]: r for r in snap["rows"]}
        assert rows["Gender"]["status"] == "left_for_you" and rows["Veteran Status"]["status"] == "left_for_you"
        assert rows["I acknowledge that I have read and agree to the terms and conditions."]["status"] == "left_for_you"
        sess.send("continue")

        snap = wait_for(sess, "done")
        assert snap["page"] == 4 and snap["titles"]["4"] == "Review" and "final review page" in snap["message"]
        assert snap["pages_done"] == [1, 2, 3]
        saved = filled.for_application(app_id)
        assert {r["page"] for r in saved} == {1, 2, 3}
        assert {r["field_label"]: r["value"] for r in saved if r["page"] == 1}["State"] == "Tennessee"
        sent = " ".join(r["messages"][0]["content"] for r in client.requests)
        assert "Gender" not in sent and "Veteran" not in sent
    finally:
        sess.send("close")
        sess.thread.join(30)


def test_form_that_does_not_move_on_stays_on_the_page(app_id, tmp_path):
    answers = {k: v for k, v in ANSWERS.items() if k != "Postal Code"}  # a required field left empty
    sess, _ = run_session(app_id, tmp_path, answers)
    try:
        wait_for(sess, "confirm")
        sess.send("confirm")
        wait_for(sess, "review")
        sess.send("continue")
        deadline_snap = None
        for _ in range(60):
            snap = sess.snapshot()
            if "didn't move on" in snap["message"]:
                deadline_snap = snap
                break
            import time
            time.sleep(0.25)
        assert deadline_snap, sess.snapshot()
        assert deadline_snap["state"] == "review" and deadline_snap["page"] == 1
        assert "required fields are empty" in deadline_snap["message"]
        sess.send("stop")
        wait_for(sess, "stopped")
    finally:
        sess.send("close")
        sess.thread.join(30)
