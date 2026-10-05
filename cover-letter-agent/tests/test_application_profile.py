"""Application profile and saved answers (Milestone 6)."""

import pytest

from storage import answers
from storage import application_profile as app_store
from storage import db


def test_defaults_mean_not_set(app_paths):
    profile = app_store.load()
    assert profile == app_store.ApplicationProfile()
    assert profile.work_authorized == profile.needs_sponsorship == profile.relocation == ""
    assert profile.country == "United States"


def test_round_trip(app_paths):
    profile = app_store.ApplicationProfile(
        street="123 Main St", city="Nashville", state="TN", postal_code="37203", work_authorized="Yes",
        needs_sponsorship="No", relocation="Open to it", start_date="Two weeks after an offer",
        salary="$110,000", heard_about="Company website")
    app_store.save(profile)
    assert app_store.load() == profile
    text = app_store.path().read_text(encoding="utf-8")
    assert "postal_code: '37203'" in text and "work_authorized: 'Yes'" in text  # quoted, so they stay text


def test_hand_edited_file(app_paths):
    app_store.path().parent.mkdir(parents=True, exist_ok=True)
    app_store.path().write_text("work_authorized: yes\nneeds_sponsorship: false\nrelocation: Maybe\n"
                                "postal_code: 37203\nunknown_field: x\n", encoding="utf-8")
    profile = app_store.load()
    assert (profile.work_authorized, profile.needs_sponsorship) == ("Yes", "No")  # YAML read these as booleans
    assert profile.relocation == "" and profile.postal_code == "37203"


def test_problems():
    assert app_store.ApplicationProfile(work_authorized="Yes", postal_code="37203").problems() == []
    assert len(app_store.ApplicationProfile(work_authorized="No", needs_sponsorship="No").problems()) == 1
    assert "ZIP code" in app_store.ApplicationProfile(postal_code="372").problems()[0]
    assert app_store.ApplicationProfile(postal_code="SW1A 1AA", country="United Kingdom").problems() == []


# --- Saved answers ------------------------------------------------------------------


@pytest.fixture
def ready(app_paths):
    db.init_db()


def test_save_list_update_delete(ready):
    first = answers.save("Why do you want to work here?", "I've used your product for years.")
    assert answers.count() == 1 and answers.list_answers()[0]["times_used"] == 0
    # The same question, differently cased and punctuated, replaces the answer.
    assert answers.save("why do you want to work here", "Updated answer.") == first
    assert answers.count() == 1 and answers.list_answers()[0]["answer"] == "Updated answer."
    second = answers.save("Are you willing to travel?", "Up to 25%.")
    answers.save("Are you willing to travel up to 25%?", "Yes, up to 25%.", answer_id=second)
    assert {a["question"] for a in answers.list_answers()} == {"why do you want to work here",
                                                               "Are you willing to travel up to 25%?"}
    with pytest.raises(answers.AnswerError, match="already has that question"):
        answers.save("Why do you want to work here?", "x", answer_id=second)
    with pytest.raises(answers.AnswerError, match="both the question and your answer"):
        answers.save("  ", "x")
    answers.delete(first)
    assert answers.count() == 1


def test_find_similar_and_record_use(ready):
    auth = answers.save("Are you legally authorized to work in the United States?", "Yes")
    answers.save("Do you require visa sponsorship now or in the future?", "No")
    answers.save("What is your favorite programming language and why?", "Python, for its readability.")
    matches = answers.find_similar("Are you authorized to work in the US?")
    assert matches[0]["id"] == auth and matches[0]["score"] >= answers.MATCH_THRESHOLD
    assert [m["answer"] for m in answers.find_similar("Will you now or in the future require sponsorship?")] == ["No"]
    assert answers.find_similar("Describe a time you led a project.") == []
    answers.record_use(auth)
    answers.record_use(auth)
    row = next(a for a in answers.list_answers() if a["id"] == auth)
    assert row["times_used"] == 2 and row["last_used_at"]


def test_similarity_ignores_filler_words():
    assert answers.similarity("Are you willing to relocate?", "Willing to relocate") == 1.0
    assert answers.similarity("Are you willing to relocate?", "What is your expected salary?") < 0.5
