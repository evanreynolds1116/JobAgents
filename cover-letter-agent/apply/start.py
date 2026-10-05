"""Set up a form-filling session for an application (spec: Ways to start, Fill application).

Milestone 7 starts from an application whose cover letter you've approved; Fill without
cover letter comes in Milestone 8.
"""

from pathlib import Path

import config
from agent import pipeline
from apply import mapping, session
from export import docx as exporter
from storage import answers as answer_store
from storage import application_profile as app_store
from storage import db, resume
from storage import profile as profile_store


class StartProblem(Exception):
    """Filling can't start yet; the message says what to do."""


def problems(app: dict) -> list[str]:
    found = []
    if not app.get("url"):
        found.append("This application has no job link. Add the company's posting link first.")
    if app.get("status") not in ("approved", "submitted") or not app.get("sent_version"):
        found.append("Approve the cover letter first. (Filling without a letter comes in a later version.)")
    if config.load_settings().key_status != "ok":
        found.append("Add your Claude API key to .env.")
    return found


def letter_text(app: dict) -> str:
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


def make_mapper(app: dict):
    settings = config.load_settings()
    client = pipeline.make_client(settings.api_key)
    sources = mapping.Sources(
        profile=profile_store.load(), answers=app_store.load(), saved_answers=answer_store.list_answers(),
        resume_text=resume.load_text(), letter_text=letter_text(app),
        has_resume_file=resume.original_file() is not None)
    return lambda fields: mapping.map_fields(client, settings.model, fields, sources)


def prepare(app_id: int, **session_args) -> session.Session:
    app = db.get_application(app_id)
    if not app:
        raise StartProblem("That application wasn't found.")
    if found := problems(app):
        raise StartProblem(" ".join(found))
    files = {"resume": resume.original_file(), "cover_letter": letter_file(app)}
    return session.Session(app_id, app["url"], make_mapper(app), files, **session_args)
