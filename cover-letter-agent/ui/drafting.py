"""Shared drafting steps for the New cover letter and review screens.

Every round saves a new version. If humanize or verify fails, the draft is still
saved (unchecked) so no work is lost, and the error is raised for the screen to show.
"""

from collections.abc import Callable

import config
from agent import pipeline
from storage import db, resume
from storage import profile as profile_store


def _client():
    settings = config.load_settings()
    return pipeline.make_client(settings.api_key), settings.model


def _fit(client, model: str, letter: str, settings: pipeline.DraftSettings,
         say: Callable[[str], None]) -> str:
    """Trim generated text that went over the word limit (your own edits are never trimmed)."""
    if pipeline.word_count(letter) > settings.word_limits[1]:
        say("Trimming to the word limit…")
        letter, _ = pipeline.trim(client, model, letter, settings.word_limits[1])
    return letter


def finish(app_id: int, letter: str, settings: pipeline.DraftSettings, feedback: str | None = None,
           smooth: bool = True, say: Callable[[str], None] = lambda _: None) -> int:
    """Steps 4 and 5 for a new letter text, then save it as a new version."""
    client, model = _client()
    app = db.get_application(app_id)
    profile = profile_store.load()
    resume_text = resume.load_text()
    notes = app.get("user_notes") or ""
    try:
        if smooth:
            say("Smoothing the wording…")
            letter, _ = pipeline.humanize(client, model, letter, profile, settings)
            letter = _fit(client, model, letter, settings, say)
        say("Checking every claim against your resume and notes…")
        checked = pipeline.verify(client, model, letter, resume_text, profile, notes, app["posting_text"])
        # Generated text gets one automatic fix-up for unsupported claims; your own edits don't.
        if smooth and pipeline.flags(checked)["claims"]:
            say("Fixing claims your sources don't support…")
            letter, _ = pipeline.fix_claims(client, model, letter, checked, resume_text, profile, notes,
                                            app["posting_text"], max_words=settings.word_limits[1])
            letter = _fit(client, model, letter, settings, say)
            say("Checking again…")
            checked = pipeline.verify(client, model, letter, resume_text, profile, notes, app["posting_text"])
    except pipeline.PipelineError:
        db.save_version(app_id, letter, resume.text_hash(resume_text), feedback=feedback)
        raise
    return db.save_version(app_id, letter, resume.text_hash(resume_text), feedback=feedback, verify=checked)


def revise(app_id: int, feedback: str, settings: pipeline.DraftSettings,
           say: Callable[[str], None] = lambda _: None) -> int:
    """Rerun steps 3 to 5 with your feedback and the latest draft."""
    client, model = _client()
    app = db.get_application(app_id)
    previous = db.latest_draft(app_id)["text"]
    say("Redrafting with your feedback…")
    letter = pipeline.draft(client, model, app["parsed_json"], app["match_json"], resume.load_text(),
                            app.get("user_notes") or "", profile_store.load(), settings,
                            previous=previous, feedback=feedback)
    return finish(app_id, letter, settings, feedback=feedback, say=say)


def save_edit(app_id: int, text: str, label: str = "Edited by hand",
              say: Callable[[str], None] = lambda _: None) -> int:
    """Your own edits are kept word for word: checked, not reworded."""
    return finish(app_id, text, settings=None, feedback=label, smooth=False, say=say)


def recheck(app_id: int, version: int) -> None:
    """Check a version again, for example after adding a fact to the notes."""
    client, model = _client()
    app = db.get_application(app_id)
    draft = next(d for d in db.list_drafts(app_id) if d["version"] == version)
    checked = pipeline.verify(client, model, draft["text"], resume.load_text(), profile_store.load(),
                              app.get("user_notes") or "", app["posting_text"])
    db.set_verify(app_id, version, checked)
