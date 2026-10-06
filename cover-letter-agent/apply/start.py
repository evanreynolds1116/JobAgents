"""Set up a form-filling session for an application (spec: Ways to start).

With an approved cover letter, the letter is uploaded or pasted where the form asks for one
(Fill application). Without one, the form is filled without a letter, and the agent pauses
if the form requires one (Fill without cover letter).
"""

from pathlib import Path

import config
from agent import pipeline
from apply import mapping, screening, session
from export import docx as exporter
from storage import answers as answer_store
from storage import application_profile as app_store
from storage import db, resume
from storage import profile as profile_store
from storage import self_id as self_id_store


class StartProblem(Exception):
    """Filling can't start yet; the message says what to do."""


def problems(app: dict) -> list[str]:
    found = []
    if not app.get("url"):
        found.append("This application has no job link. Add the company's posting link first.")
    if config.load_settings().key_status != "ok":
        found.append("Add your Claude API key to .env.")
    return found


def has_letter(app: dict) -> bool:
    return app.get("status") in ("approved", "submitted") and bool(app.get("sent_version"))


def letter_text(app: dict) -> str:
    if not has_letter(app):
        return ""
    drafts = db.list_drafts(app["id"])
    version = next((d for d in drafts if d["version"] == app.get("sent_version")), None)
    return version["text"] if version else ""


def letter_file(app: dict) -> Path:
    """The approved letter as a PDF for upload, or a .docx if no PDF maker is installed."""
    drafts = db.list_drafts(app["id"])
    try:
        return exporter.export_pdf(app, drafts, profile_store.load())
    except exporter.PdfUnavailable:
        return exporter.export_docx(app, drafts, profile_store.load())


def make_steps(app: dict):
    """The mapper, the screening-answer drafter and the after-fill step for a session."""
    settings = config.load_settings()
    client = pipeline.make_client(settings.api_key)
    profile = profile_store.load()
    sources = mapping.Sources(
        profile=profile, answers=app_store.load(), saved_answers=answer_store.list_answers(),
        resume_text=resume.load_text(), letter_text=letter_text(app),
        has_resume_file=resume.original_file() is not None, self_id=self_id_store.load())

    def mapper(fields):
        return mapping.map_fields(client, settings.model, fields, sources)

    def drafter(fields, decisions):
        by_key = {f.key: f for f in fields}
        questions = [by_key[d.key] for d in decisions if screening.is_screening_question(by_key[d.key], d)]
        drafts = screening.draft_answers(client, settings.model, questions, sources, app.get("posting_text") or "",
                                         app.get("user_notes") or "", profile.writing_samples)
        return screening.apply_drafts(fields, decisions, drafts)

    def after_fill(fields, decisions):
        record_saved_answer_use(fields, decisions)

    return mapper, drafter, after_fill


def record_saved_answer_use(fields, decisions) -> None:
    """Count each saved answer the agent reused (Saved answers: times used)."""
    by_key = {f.key: f for f in fields}
    for d in decisions:
        if d.source == "saved_answer" and d.status in ("filled", "review"):
            if match := answer_store.find_similar(by_key[d.key].label, limit=1):
                answer_store.record_use(match[0]["id"])


def prepare(app_id: int, **session_args) -> session.Session:
    app = db.get_application(app_id)
    if not app:
        raise StartProblem("That application wasn't found.")
    if found := problems(app):
        raise StartProblem(" ".join(found))
    with_letter = has_letter(app)
    files = {"resume": resume.original_file(), "cover_letter": letter_file(app) if with_letter else None}
    mapper, drafter, after_fill = make_steps(app)
    return session.Session(app_id, app["url"], mapper, files, drafter=drafter, after_fill=after_fill,
                           has_letter=with_letter, **session_args)
