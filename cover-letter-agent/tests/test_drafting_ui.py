"""New cover letter and review screens, with the fetcher and Claude faked."""

import copy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from agent import fetch, pipeline
from storage import db, resume
from ui import nav
from ui.review import letter_html, remove_sentence

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
FALSE = "I ran the Nashville Marathon expo for 30,000 runners."
LETTER = (f"Dear Priya Raman,\n\nI'd like to run your newsletter. {FALSE} It costs $0 to say so.\n\n"
          "Thanks for your time,\nJordan Avery")
CLAIMS = [
    {"claim": "I'd like to run your newsletter.", "supported": True, "source": "posting",
     "evidence": "run our email newsletter", "reason": ""},
    {"claim": FALSE, "supported": False, "source": "none", "evidence": "",
     "reason": "None of your sources mention the Nashville Marathon."},
]


class Calls:
    def __init__(self):
        self.counts = {"fetch": 0, "parse": 0, "match": 0, "draft": 0, "humanize": 0, "verify": 0, "fix": 0}
        self.went = []
        self.parsed = dict(PARSED)
        self.fail_match = 0
        self.fail_verify = 0
        self.feedback = []


def fake_verify_result(letter: str, notes: str) -> dict:
    """Like the real verifier: claims that are in the notes count as supported."""
    claims = []
    for c in copy.deepcopy(CLAIMS):
        if c["claim"] not in letter:
            continue
        if not c["supported"] and c["claim"] in notes:
            c.update(supported=True, source="notes", evidence=c["claim"], reason="")
        c["in_letter"] = True
        claims.append(c)
    return {"claims": claims, "style_flags": [], "lint": []}


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

    def fake_draft(client, model, parsed, matches, resume_text, notes, profile, settings,
                   previous=None, feedback=None):
        c.counts["draft"] += 1
        c.feedback.append(feedback)
        return LETTER if not feedback else LETTER.replace("run your newsletter", "run your festivals")

    def fake_humanize(client, model, letter, profile, settings):
        c.counts["humanize"] += 1
        return letter, []

    def fake_verify(client, model, letter, resume_text, profile, notes, posting_text):
        c.counts["verify"] += 1
        if c.fail_verify:
            c.fail_verify -= 1
            raise pipeline.PipelineError("Claude took too long to respond.")
        return fake_verify_result(letter, notes)

    def fake_fix(client, model, letter, checked, resume_text, profile, notes, posting_text):
        c.counts["fix"] += 1
        return letter.replace(f" {FALSE}", ""), [f"Removed: {FALSE}"]

    monkeypatch.setattr(fetch, "fetch", fake_fetch)
    monkeypatch.setattr(pipeline, "make_client", lambda key: object())
    monkeypatch.setattr(pipeline, "parse_job", fake_parse)
    monkeypatch.setattr(pipeline, "match", fake_match)
    monkeypatch.setattr(pipeline, "draft", fake_draft)
    monkeypatch.setattr(pipeline, "humanize", fake_humanize)
    monkeypatch.setattr(pipeline, "verify", fake_verify)
    monkeypatch.setattr(pipeline, "fix_claims", fake_fix)
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


def click(at, label, nth=0):
    [b for b in at.button if b.label == label][nth].click().run()
    assert not at.exception, at.exception


def markdown_text(at) -> str:
    return "\n".join(m.value for m in at.markdown)


# --- New cover letter ----------------------------------------------------------


def test_without_resume_points_to_profile(app_paths):
    db.init_db()
    at = open_new_letter()
    assert "Add your resume first" in at.markdown[1].value
    assert any(b.label == "Go to Profile & resume" for b in at.button)


def test_link_to_checked_draft(calls):
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
    assert draft["version"] == 1 and draft["resume_hash"] == resume.text_hash()
    # The unsupported claim was fixed automatically, then the letter was checked again.
    assert FALSE not in draft["text"] and "run your newsletter" in draft["text"]
    assert calls.counts["humanize"] == 1 and calls.counts["fix"] == 1 and calls.counts["verify"] == 2
    assert pipeline.flag_count(draft["verify_json"]) == 0


def test_check_failure_still_saves_the_draft(calls):
    calls.fail_verify = 1
    at = open_new_letter()
    at.text_input(key="nl_url").input("https://harpeth.example/careers/marketing")
    click(at, "Generate draft")
    assert calls.went == [("review", {"app": 1})]
    (draft,) = db.list_drafts(1)
    assert draft["verify_json"] is None
    assert "couldn't be checked" in at.session_state["rv_flash"]


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
    assert "You already have an application for Marketing Coordinator at Harpeth Outdoor Co." in markdown_text(at)
    click(at, "Draft a new version")
    assert [d["version"] for d in db.list_drafts(1)] == [2, 1]
    assert calls.counts == {"fetch": 1, "parse": 1, "match": 2, "draft": 2, "humanize": 2, "verify": 4, "fix": 2}


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


def make_app(text=LETTER, verify="auto", notes="") -> int:
    app_id = db.create_application("https://harpeth.example/job", POSTING, notes)
    db.update_application(app_id, parsed_json=PARSED, match_json=MATCHES,
                          company=PARSED["company"], title=PARSED["title"])
    db.add_draft(app_id, text, "hash1", verify=fake_verify_result(text, notes) if verify == "auto" else verify)
    return app_id


def approve_button(at):
    return next(b for b in at.button if b.label == "Approve letter")


def test_review_shows_flags_match_and_versions(calls):
    app_id = make_app()
    db.add_draft(app_id, LETTER.replace("newsletter", "festivals"), "hash1", feedback="Lead with festivals",
                 verify=fake_verify_result(LETTER, ""))
    at = open_review(app_id)
    assert at.title[0].value == "Marketing Coordinator"
    page = markdown_text(at)
    assert "Draft · version 2" in page
    assert '<mark class="ja-flag-claim" title="None of your sources mention the Nashville Marathon.">' in page
    assert "festivals" in page
    assert "Needs your review (1)" in [s.value for s in at.subheader]
    assert at.radio(key=f"rv_version_{app_id}").value == 2
    assert "Canva" in page and "Strong" in page


def test_flagged_letter_needs_review_tick_before_approval(calls):
    app_id = make_app()
    at = open_review(app_id)
    assert approve_button(at).disabled
    at.checkbox(key=f"rv_reviewed_{app_id}_1").check().run()
    assert not approve_button(at).disabled
    click(at, "Approve letter")
    app = db.get_application(app_id)
    assert app["status"] == "approved" and app["sent_version"] == 1 and app["approved_at"]
    assert "Approved · version 1" in markdown_text(at)
    assert "Exports version 1, the one you approved." in [c.value for c in at.caption]
    assert not any(b.disabled for b in at.button if b.label.startswith("Export"))


def test_clean_letter_can_be_approved_directly(calls):
    clean = LETTER.replace(f" {FALSE}", "")
    app_id = make_app(clean)
    at = open_review(app_id)
    assert "All clear" in [s.value for s in at.subheader]
    assert not approve_button(at).disabled


def test_export_locked_until_approved(calls):
    at = open_review(make_app())
    assert all(b.disabled for b in at.button if b.label.startswith("Export"))
    assert "Export unlocks after you approve." in [c.value for c in at.caption]


def test_editing_after_approval_returns_to_draft(calls):
    app_id = make_app()
    db.approve(app_id, 1)
    at = open_review(app_id)
    assert "Editing the letter now would return it to draft." in [c.value for c in at.caption]
    click(at, "Edit letter")
    at.text_area(key="rv_edit_text").input(LETTER.replace("Jordan Avery", "Jordan A."))
    click(at, "Save edits")
    app = db.get_application(app_id)
    assert app["status"] == "draft" and app["sent_version"] is None
    latest = db.latest_draft(app_id)
    assert latest["version"] == 2 and latest["feedback"] == "Edited by hand"
    assert latest["text"].endswith("Jordan A.")
    assert calls.counts["humanize"] == 0 and calls.counts["fix"] == 0  # your words kept word for word
    assert calls.counts["verify"] == 1  # but still checked


def test_ask_for_changes_saves_a_new_version(calls):
    app_id = make_app()
    at = open_review(app_id)
    at.text_area(key="rv_feedback").input("Lead with the festivals").run()
    click(at, "Redraft")
    latest = db.latest_draft(app_id)
    assert latest["version"] == 2 and latest["feedback"] == "Lead with the festivals"
    assert "festivals" in latest["text"]
    assert calls.feedback == ["Lead with the festivals"]


def test_its_true_adds_claim_to_notes_and_rechecks(calls):
    app_id = make_app()
    at = open_review(app_id)
    click(at, "It's true: add to notes")
    assert FALSE in db.get_application(app_id)["user_notes"]
    assert db.latest_draft(app_id)["version"] == 1  # letter unchanged, just checked again
    assert pipeline.flag_count(db.latest_draft(app_id)["verify_json"]) == 0
    assert "All clear" in [s.value for s in at.subheader]


def test_remove_sentence_button(calls):
    app_id = make_app()
    at = open_review(app_id)
    click(at, "Remove sentence")
    latest = db.latest_draft(app_id)
    assert latest["version"] == 2 and FALSE not in latest["text"]
    assert "I'd like to run your newsletter. It costs $0 to say so." in latest["text"]


def test_unchecked_version_can_be_checked(calls):
    app_id = make_app(verify=None)
    at = open_review(app_id)
    assert "Not checked yet" in [s.value for s in at.subheader]
    assert approve_button(at).disabled
    click(at, "Check again")
    assert db.latest_draft(app_id)["verify_json"] is not None


def test_restore_an_older_version(calls):
    app_id = make_app()
    db.add_draft(app_id, "Dear Priya,\n\nSecond.\n\nJordan", "hash1", feedback="Shorter")
    at = open_review(app_id)
    at.radio(key=f"rv_version_{app_id}").set_value(1).run()
    assert "You're viewing **version 1**. The latest is version 2." in markdown_text(at)
    click(at, "Use this version")
    latest = db.latest_draft(app_id)
    assert latest["version"] == 3 and latest["text"] == LETTER and latest["feedback"] == "Restored version 1"


def test_review_without_application(app_paths):
    db.init_db()
    assert "No letter is open" in open_review(None).info[0].value
    assert "No letter is open" in open_review(99).info[0].value


# --- Helpers ---------------------------------------------------------------------


def test_letter_html_escapes_and_highlights():
    text = "Dear <Team>,\n\nI built X & Y. I won a Nobel Prize.\nThanks"
    verify = {"claims": [{"claim": "I won a Nobel Prize.", "supported": False, "reason": 'Not in "resume"'}],
              "style_flags": [{"text": "I built X & Y.", "issue": "Stiff"}], "lint": []}
    html = letter_html(text, verify)
    assert html.startswith('<div class="ja-letter"><p>Dear &lt;Team&gt;,</p>')
    assert '<mark class="ja-flag-style" title="Stiff">I built X &amp; Y.</mark>' in html
    assert '<mark class="ja-flag-claim" title="Not in &quot;resume&quot;">I won a Nobel Prize.</mark><br>Thanks' in html


def test_remove_sentence_keeps_the_rest():
    text = "Dear Priya,\n\nFirst sentence. Remove me now. Last one!\n\nThanks,\nJordan"
    assert remove_sentence(text, "Remove me now.") == "Dear Priya,\n\nFirst sentence. Last one!\n\nThanks,\nJordan"
    assert remove_sentence(text, "not there") == text


def test_fix_up_runs_only_when_claims_are_flagged(calls, monkeypatch):
    clean = LETTER.replace(f" {FALSE}", "")
    monkeypatch.setattr(pipeline, "draft", lambda *a, **k: clean)
    at = open_new_letter()
    at.text_input(key="nl_url").input("https://harpeth.example/careers/marketing")
    click(at, "Generate draft")
    assert calls.counts["fix"] == 0 and calls.counts["verify"] == 1


def test_claims_still_unsupported_after_fix_stay_flagged(calls, monkeypatch):
    monkeypatch.setattr(pipeline, "fix_claims", lambda *a: (a[2], ["Couldn't fix"]))  # fix-up changes nothing
    at = open_new_letter()
    at.text_input(key="nl_url").input("https://harpeth.example/careers/marketing")
    click(at, "Generate draft")
    (draft,) = db.list_drafts(1)
    assert FALSE in draft["text"] and pipeline.flag_count(draft["verify_json"]) == 1
