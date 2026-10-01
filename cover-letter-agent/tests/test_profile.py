from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import config
from storage import profile as profile_store
from storage import resume

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# --- profile.yaml ----------------------------------------------------------


def test_defaults_when_no_file(app_paths):
    p = profile_store.load()
    assert p.tone == "Professional and warm"
    assert p.length == "250–400 words"
    assert p.sign_off == "Thanks for your time,"
    assert p.writing_samples == []


def test_round_trip_keeps_multiline_and_unicode(app_paths):
    sample = "Dear Ms. Núñez,\n\nI've followed your club for years — here's why.\n"
    p = profile_store.Profile(
        name="Jordan Avery", email="jordan@example.com", city="Nashville, TN",
        tone="More casual", writing_samples=[sample, "  ", "Second sample."],
        never_mention="My career break in 2022",
    )
    profile_store.save(p)
    loaded = profile_store.load()
    assert loaded.name == "Jordan Avery"
    assert loaded.tone == "More casual"
    assert loaded.writing_samples == [sample.strip(), "Second sample."]
    raw = profile_store.profile_path().read_text(encoding="utf-8")
    assert "writing_samples:\n- |" in raw  # readable block style
    assert "Núñez" in raw


def test_hand_edited_file_is_tolerated(app_paths):
    config.DATA_DIR.mkdir(parents=True)
    profile_store.profile_path().write_text(
        "name: Jordan\nphone: 5555550142\ntone: Shouty\nunknown_key: x\nwriting_samples:\n",
        encoding="utf-8",
    )
    p = profile_store.load()
    assert p.name == "Jordan"
    assert p.phone == "5555550142"
    assert p.tone == "Professional and warm"  # unknown value falls back to default
    assert p.writing_samples == []


def test_problems_flag_bad_email_and_link():
    p = profile_store.Profile(email="jordan.example.com", link="linkedin.com/in/jordan")
    assert len(p.problems()) == 2
    assert profile_store.Profile(email="j@example.com", link="https://x.example").problems() == []


# --- Profile screen --------------------------------------------------------


@pytest.fixture
def at(app_paths):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n")
    return open_profile()


def _profile_script():
    import app

    app.profile_page()


def open_profile():
    at = AppTest.from_function(_profile_script, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "Profile & resume"
    return at


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception, at.exception


def test_edits_persist_after_restart(at):
    at.text_input(key="pf_name").input("Jordan Avery")
    at.text_input(key="pf_email").input("jordan@example.com")
    at.selectbox(key="pf_tone").select("More formal")
    at.text_area(key="pf_sample_0").input("A past cover letter I liked.")
    at.text_area(key="pf_resume_text").input("# Jordan Avery\n\n## Experience\n\nEdited by hand.")
    at.run()
    assert any(c.value == "You have unsaved changes." for c in at.caption)
    click(at, "Save changes")
    assert at.success[0].value == "Saved."
    assert not any(c.value == "You have unsaved changes." for c in at.caption)

    # A fresh session reads everything back from disk, as after a restart.
    again = open_profile()
    assert again.text_input(key="pf_name").value == "Jordan Avery"
    assert again.selectbox(key="pf_tone").value == "More formal"
    assert again.text_area(key="pf_sample_0").value == "A past cover letter I liked."
    assert "Edited by hand." in again.text_area(key="pf_resume_text").value


def test_add_second_writing_sample(at):
    at.text_area(key="pf_sample_0").input("First sample.")
    click(at, "Add another sample")
    at.text_area(key="pf_sample_1").input("Second sample.")
    click(at, "Save changes")
    assert profile_store.load().writing_samples == ["First sample.", "Second sample."]


def test_save_warns_about_bad_email(at):
    at.text_input(key="pf_email").input("not-an-email")
    click(at, "Save changes")
    assert "email" in at.warning[0].value


def test_upload_converts_resume(at):
    pdf = (FIXTURES / "resume_one_column.pdf").read_bytes()
    at.file_uploader[0].upload("resume.pdf", pdf, "application/pdf").run()
    assert not at.exception, at.exception
    assert "Converted" in at.info[0].value
    assert at.text_area(key="pf_resume_text").value.startswith("# Jordan Avery")
    assert resume.original_file().name == "resume_original.pdf"
    assert resume.has_resume()


def test_upload_error_is_shown(at):
    at.file_uploader[0].upload("resume.pdf", b"not a pdf", "application/pdf").run()
    assert not at.exception, at.exception
    assert "couldn't be opened" in at.error[0].value
    assert not resume.has_resume()
