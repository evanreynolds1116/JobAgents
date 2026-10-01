import io
import os
import subprocess
import sys
from datetime import date

import docx
import pytest

from export import docx as exporter
from storage.profile import Profile

PROFILE = Profile(name="Jordan Avery", email="jordan@example.com", phone="(555) 555-0142",
                  city="Nashville, TN", linkedin="https://www.linkedin.com/in/jordan-example/")
APPROVED = {"id": 1, "company": "Summit City Hockey Club", "title": "Social Media Coordinator",
            "status": "approved", "sent_version": 1}
DRAFTS = [
    {"version": 2, "text": "Dear Dana,\n\nA newer draft you never approved.\n\nThanks,\nJordan Avery"},
    {"version": 1, "text": "Dear Dana,\n\nThe **approved** letter, $60k and all.\n\nThanks for your time,\nJordan Avery"},
]


def paragraphs(data: bytes) -> list[str]:
    return [p.text for p in docx.Document(io.BytesIO(data)).paragraphs]


def test_docx_layout():
    data = exporter.build_docx(DRAFTS[1]["text"], PROFILE, when=date(2026, 10, 1))
    assert paragraphs(data) == [
        "Jordan Avery",
        "Nashville, TN · jordan@example.com · +1 (555) 555-0142 · linkedin.com/in/jordan-example",
        "October 1, 2026",
        "Dear Dana,",
        "The approved letter, $60k and all.",
        "Thanks for your time,\nJordan Avery",  # sign-off and name on separate lines
    ]


def test_docx_without_contact_details():
    data = exporter.build_docx("Dear Dana,\n\nHello.", Profile(), when=date(2026, 10, 1))
    assert paragraphs(data) == ["October 1, 2026", "Dear Dana,", "Hello."]


def test_file_name_follows_spec_and_is_safe_on_windows():
    assert exporter.file_stem(APPROVED) == "Summit City Hockey Club - Social Media Coordinator - Cover Letter"
    odd = {"company": 'Acme: "AI"/Labs', "title": "Engineer | Platform?"}
    assert exporter.file_stem(odd) == "Acme AILabs - Engineer Platform - Cover Letter"


def test_export_uses_the_approved_version(tmp_path):
    path = exporter.export_docx(APPROVED, DRAFTS, PROFILE, tmp_path)
    assert path == tmp_path / "Summit City Hockey Club - Social Media Coordinator - Cover Letter.docx"
    text = "\n".join(paragraphs(path.read_bytes()))
    assert "The approved letter" in text and "never approved" not in text


@pytest.mark.parametrize("app", [
    {**APPROVED, "status": "draft", "sent_version": None},
    {**APPROVED, "status": "archived"},
    {**APPROVED, "sent_version": None},
])
def test_export_refused_unless_approved(tmp_path, app):
    with pytest.raises(exporter.NotApproved):
        exporter.export_docx(app, DRAFTS, PROFILE, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_submitted_letters_still_export(tmp_path):
    assert exporter.export_docx({**APPROVED, "status": "submitted"}, DRAFTS, PROFILE, tmp_path).exists()


def test_pdf_via_word(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        open(cmd[-1], "wb").write(b"%PDF-1.7")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(exporter.subprocess, "run", fake_run)
    pdf = exporter.export_pdf(APPROVED, DRAFTS, PROFILE, tmp_path)
    assert pdf.suffix == ".pdf" and pdf.read_bytes() == b"%PDF-1.7"
    assert calls[0][0] == sys.executable and "docx2pdf" in calls[0][2]


def test_pdf_unavailable_keeps_the_docx(tmp_path, monkeypatch):
    def failing_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(exporter.subprocess, "run", failing_run)
    monkeypatch.setattr(exporter, "_soffice", lambda: None)
    with pytest.raises(exporter.PdfUnavailable, match="Microsoft Word or LibreOffice"):
        exporter.export_pdf(APPROVED, DRAFTS, PROFILE, tmp_path)
    assert (tmp_path / f"{exporter.file_stem(APPROVED)}.docx").exists()


@pytest.mark.skipif(os.environ.get("JOBAGENTS_PDF_TEST") != "1",
                    reason="opens Microsoft Word; set JOBAGENTS_PDF_TEST=1 to run")
def test_real_pdf_conversion(tmp_path):
    pdf = exporter.export_pdf(APPROVED, DRAFTS, PROFILE, tmp_path)
    assert pdf.read_bytes().startswith(b"%PDF")
