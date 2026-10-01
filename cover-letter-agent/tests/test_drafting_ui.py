"""New cover letter and review screens, with the fetcher and Claude faked."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from agent import fetch, pipeline
from storage import db, resume
from ui import nav

FIXTURES = Path(__file__).resolve().parent / "fixtures"
POSTING = fetch.extract((FIXTURES / "postings" / "plain_company_page.html").read_text(encoding="utf-8")).text
PARSED = {
    "company": "Harpeth Outdoor Co.", "title": "Marketing Coordinator", "location": "Franklin, TN",
    "must_have": ["2+ years in a marketing coordinator role"], "nice_to_have": ["Canva"],
    "responsibilities": ["Run the newsletter"], "keywords": ["email"], "contact_name": "Priya Raman",
    "tone_signals": "Friendly.", "several_jobs": False,
}
MATCHES = {"matches": [{
    "requirement": "Canva", "kind": "nice_to_have", "strength": "strong", "feature": True,
    "evidence": [{"quote": "Canva and Adobe Express", "source": "resume"}],
}]}
LETTER = "Dear Priya Raman,\n\nI'd like to run your newsletter. It costs $0 to say so.\n\nThanks for your time,\nJordan Avery"


class Calls:
    def __init__(self):
        self.counts = {"fetch": 0, "parse": 0, "match": 0, "draft": 0}
        self.went = []
        self.parsed = dict(PARSED)
        self.fail_match = 0


@pytest.fixture
def calls(app_paths, monkeypatch):
    db.init_db()
    resume.save_text(resume.convert("r.pdf", (FIXTURES / "resume_one_column.pdf").read_bytes()))
    c = Calls()

    def fake_fetch(url, client=None):
        c.counts["fetch"] += 1
        if "blocked" in url:
            return fetch.FetchResult(False, url, reason="The site blocked the request or needs a login.")
        return fetch.FetchResult(True, url, text=POSTING)

    def fake_parse(client, model, text):
        c.counts["parse"] += 1
        return dict(c.parsed)

    def fake_match(client, model, parsed, resume_text, notes):
        c.counts["match"] += 1
        if c.fail_match:
            c.fail_match -= 1
            raise pipeline.PipelineError("Claude had a server problem.", raw="raw model output")
        return MATCHES

    def fake_draft(client, model, parsed, matches, resume_text, notes, profile, settings):
        c.counts["draft"] += 1
        return LETTER

    monkeypatch.setattr(fetch, "fetch", fake_fetch)
    monkeypatch.setattr(pipeline, "make_client", lambda key: object())
    monkeypatch.setattr(pipeline, "parse_job", fake_parse)
    monkeypatch.setattr(pipeline, "match", fake_match)
    monkeypatch.setattr(pipeline, "draft", fake_draft)
    monkeypatch.setattr(nav, "go", lambda key, **params: c.went.append((key, params)))
    return c


def _new_letter_script():
    from ui import new_letter

    new_letter.new_letter_page()


def open_new_letter():
    at = AppTest.from_function(_new_letter_script, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception, at.exception


def test_without_resume_points_to_profile(app_paths):
    db.init_db()
    at = open_new_letter()
    assert "Add your resume first" in at.markdown[1].value
    assert any(b.label == "Go to Profile & resume" for b in at.button)


def test_link_to_draft(calls):
    at = open_new_letter()
    at.text_input(key="nl_url").input("https://harpeth.example/careers/marketing?utm_source=x")
    at.text_area(key="nl_notes").input("I paddle the Harpeth most weekends.")
    click(at, "Generate draft")
    assert calls.went == [("review", {"app": 1})]
    app = db.get_application(1)
    assert app["url"] == "https://harpeth.example/careers/marketing"
    assert app["company"] == "Harpeth Outdoor Co." and app["title"] == "Marketing Coordinator"
    assert app["user_notes"] == "I paddle the Harpeth most weekends."
    assert app["status"] == "draft" and app["match_json"] == MATCHES
    (draft,) = db.list_drafts(1)
    assert draft["version"] == 1 and draft["text"] == LETTER and draft["resume_hash"] == resume.text_hash()


def test_blocked_site_falls_back_to_paste(calls):
    at = open_new_letter()
    at.text_input(key="nl_url").input("https://blocked.example/job")
    click(at, "Generate draft")
    assert "Couldn't read this page" in at.warning[0].value
    assert calls.counts["parse"] == 0
    at.text_area(key="nl_paste").input(POSTING)
    click(at, "Generate draft")
    assert calls.counts["fetch"] == 1  # pasted text is used, not fetched again
    assert calls.went == [("review", {"app": 1})]
    assert db.get_application(1)["url"] == "https://blocked.example/job"  # kept for the record


def test_paste_without_link(calls):
    at = open_new_letter()
    click(at, "Paste the posting text instead")
    at.text_area(key="nl_paste").input(POSTING)
    click(at, "Generate draft")
    assert calls.counts["fetch"] == 0
    assert db.get_application(1)["url"] is None


def test_nothing_to_work_from(calls):
    at = open_new_letter()
    click(at, "Generate draft")
    assert "Add a job posting link" in at.error[0].value


def test_same_url_offers_existing_application(calls):
    at = open_new_letter()
    at.text_input(key="nl_url").input("https://harpeth.example/careers/marketing")
    click(at, "Generate draft")
    at = open_new_letter()
    at.text_input(key="nl_url").input("https://harpeth.example/careers/marketing/")
    click(at, "Generate draft")
    assert any("You already have an application for Marketing Coordinator at Harpeth Outdoor Co." in m.value
               for m in at.markdown)
    click(at, "Draft a new version")
    assert [d["version"] for d in db.list_drafts(1)] == [2, 1]
    assert calls.counts == {"fetch": 1, "parse": 1, "match": 2, "draft": 2}


def test_unclear_title_is_confirmed_first(calls):
    calls.parsed["title"] = None
    calls.parsed["several_jobs"] = True
    at = open_new_letter()
    at.text_input(key="nl_url").input("https://harpeth.example/careers")
    click(at, "Generate draft")
    assert at.subheader[0].value == "Check the company and job title"
    assert calls.counts["match"] == 0
    at.text_input(key="nl_confirm_title").input("Marketing Coordinator").run()  # leaving the field reruns
    click(at, "Continue drafting")
    assert calls.went == [("review", {"app": 1})]
    parsed = db.get_application(1)["parsed_json"]
    assert parsed["title"] == "Marketing Coordinator" and parsed["several_jobs"] is False


def test_failure_keeps_work_and_try_again_resumes(calls):
    calls.fail_match = 1
    at = open_new_letter()
    at.text_input(key="nl_url").input("https://harpeth.example/careers/marketing")
    click(at, "Generate draft")
    assert "Drafting stopped" in at.error[0].value
    assert db.get_application(1)["parsed_json"]["company"] == "Harpeth Outdoor Co."  # parse kept
    assert at.expander[0].label == "Debug details"
    click(at, "Try again")
    assert calls.counts["parse"] == 1 and calls.counts["match"] == 2
    assert calls.went == [("review", {"app": 1})]


# --- Review screen -------------------------------------------------------------


def _review_script():
    from ui import review

    review.review_page()


def open_review(app_id):
    at = AppTest.from_function(_review_script, default_timeout=30)
    if app_id is not None:
        at.query_params["app"] = str(app_id)
    at.run()
    assert not at.exception, at.exception
    return at


def test_review_shows_summary_match_and_draft(app_paths):
    db.init_db()
    app_id = db.create_application("https://harpeth.example/job", POSTING, "")
    db.update_application(app_id, parsed_json=PARSED, match_json=MATCHES,
                          company=PARSED["company"], title=PARSED["title"])
    db.add_draft(app_id, LETTER, "hash1")
    db.add_draft(app_id, LETTER.replace("newsletter", "festivals"), "hash1", feedback="Lead with festivals")
    at = open_review(app_id)
    assert at.title[0].value == "Marketing Coordinator"
    assert at.caption[0].value == "Draft · version 2"
    letter = next(m.value for m in at.markdown if m.value.startswith("Dear Priya"))
    assert "festivals" in letter and r"\$0" in letter  # $ shown literally
    assert "Thanks for your time,  \nJordan Avery" in letter  # sign-off and name on separate lines
    assert at.selectbox(key=f"rv_version_{app_id}").value == 2
    assert any("Canva" in m.value and "Strong" in m.value for m in at.markdown)


def test_review_without_application(app_paths):
    db.init_db()
    assert "No letter is open" in open_review(None).info[0].value
    assert "No letter is open" in open_review(99).info[0].value
