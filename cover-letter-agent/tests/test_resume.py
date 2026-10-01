import io
from pathlib import Path

import docx
import pytest
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import parse_xml
from docx.oxml.ns import qn

import config
from storage import resume

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SECTIONS = ["SUMMARY", "EXPERIENCE", "EDUCATION", "SKILLS"]
FACTS = [
    "Jordan Avery",
    "jordan.avery@example.com",
    "(555) 555-0142",
    "Riverbend Youth Soccer League",
    "2,400 to 9,100",
    "38%",
    "3,000 subscribers",
    "Middle Tennessee State University",
    "Google Analytics",
]


def convert_fixture(name):
    return resume.convert(name, (FIXTURES / name).read_bytes())


def lines(md):
    return md.splitlines()


@pytest.mark.parametrize("name", ["resume_one_column.pdf", "resume_two_column.pdf"])
def test_pdf_keeps_every_section_and_fact(name):
    md = convert_fixture(name)
    assert lines(md)[0] == "# Jordan Avery"
    for section in SECTIONS:
        assert f"## {section}" in lines(md)
    flat = " ".join(md.split())
    for fact in FACTS:
        assert fact in flat, fact
    assert "- Grew Instagram following from 2,400 to 9,100 in two seasons." in lines(md)


def test_pdf_one_column_keeps_order():
    md = convert_fixture("resume_one_column.pdf")
    positions = [md.index(f"## {s}") for s in SECTIONS]
    assert positions == sorted(positions)


def test_pdf_two_columns_are_not_interleaved():
    md = convert_fixture("resume_two_column.pdf")
    # The contact line stays whole, and each column is read top to bottom.
    assert "jordan.avery@example.com · (555) 555-0142 · Nashville, TN" in md
    assert md.index("## SKILLS") < md.index("Event planning") < md.index("## EDUCATION")
    assert md.index("## SUMMARY") < md.index("## EXPERIENCE") < md.index("25 community events")
    experience = md[md.index("## EXPERIENCE"):]
    assert "Hootsuite" not in experience


# --- .docx -----------------------------------------------------------------

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
V = "urn:schemas-microsoft-com:vml"


def text_box_run(text):
    """A text box the way Word saves one: a modern copy plus a VML fallback."""
    box = f'<w:txbxContent><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:txbxContent>'
    return parse_xml(
        f'<w:r xmlns:w="{W}" xmlns:mc="{MC}" xmlns:v="{V}"><mc:AlternateContent>'
        f'<mc:Choice Requires="wps"><w:pict><v:shape><v:textbox>{box}</v:textbox></v:shape></w:pict></mc:Choice>'
        f'<mc:Fallback><w:pict><v:shape><v:textbox>{box}</v:textbox></v:shape></w:pict></mc:Fallback>'
        f'</mc:AlternateContent></w:r>'
    )


def add_hyperlink(paragraph, label, url):
    r_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = parse_xml(
        f'<w:hyperlink xmlns:w="{W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        f'r:id="{r_id}"><w:r><w:t>{label}</w:t></w:r></w:hyperlink>'
    )
    paragraph._p.append(link)


def make_docx() -> bytes:
    d = docx.Document()
    d.sections[0].header.paragraphs[0].text = "jordan.avery@example.com · (555) 555-0142"
    d.add_paragraph("Jordan Avery", style="Title")
    contact = d.add_paragraph("Portfolio: ")
    add_hyperlink(contact, "LinkedIn", "https://www.linkedin.com/in/jordanavery-example")
    d.add_paragraph("Summary", style="Heading 1")
    d.add_paragraph("Marketing coordinator with five years of experience.")
    d.add_paragraph("Experience", style="Heading 1")
    job = d.add_paragraph()
    job.add_run("Social Media Manager, Riverbend Youth Soccer League").bold = True
    d.add_paragraph("Cut paid ad spend by 38%.", style="List Bullet")
    d.add_paragraph("EDUCATION")  # heading typed in caps, no heading style
    table = d.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Middle Tennessee State University"
    table.cell(0, 1).text = "2019"
    note = d.add_paragraph()
    note._p.append(text_box_run("Volunteer: Nashville Predators Foundation"))
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_docx_structure_and_hidden_places():
    md = resume.convert("resume.docx", make_docx())
    out = lines(md)
    assert out[0] == "jordan.avery@example.com · (555) 555-0142"  # page header
    assert "# Jordan Avery" in out
    assert "## Summary" in out and "## Experience" in out
    assert "## EDUCATION" in out
    assert "**Social Media Manager, Riverbend Youth Soccer League**" in out
    assert "- Cut paid ad spend by 38%." in out
    assert "Middle Tennessee State University" in out and "2019" in out  # table
    assert "Portfolio: [LinkedIn](https://www.linkedin.com/in/jordanavery-example)" in out
    assert md.count("Nashville Predators Foundation") == 1  # text box, read once


# --- Errors and storage ----------------------------------------------------


def test_rejects_other_file_types():
    with pytest.raises(resume.ConversionError):
        resume.convert("resume.txt", b"hello")


def test_rejects_damaged_files():
    with pytest.raises(resume.ConversionError):
        resume.convert("resume.pdf", b"not a pdf")
    with pytest.raises(resume.ConversionError):
        resume.convert("resume.docx", b"not a docx")


def test_rejects_file_without_text():
    d = docx.Document()
    buf = io.BytesIO()
    d.save(buf)
    with pytest.raises(resume.ConversionError, match="Couldn't find any text"):
        resume.convert("empty.docx", buf.getvalue())


def test_import_stores_original_and_text(app_paths):
    pdf = (FIXTURES / "resume_one_column.pdf").read_bytes()
    text = resume.import_file("My Resume.PDF", pdf)
    assert resume.load_text() == text
    assert resume.original_file() == config.DATA_DIR / "resume_original.pdf"
    assert resume.original_file().read_bytes() == pdf

    # Replacing with a .docx removes the old PDF.
    resume.import_file("resume.docx", make_docx())
    assert resume.original_file() == config.DATA_DIR / "resume_original.docx"
    assert not (config.DATA_DIR / "resume_original.pdf").exists()


def test_edits_persist_and_hash_changes(app_paths):
    assert not resume.has_resume()
    resume.save_text("# Jordan Avery\n\nEdited by hand.")
    assert resume.load_text() == "# Jordan Avery\n\nEdited by hand.\n"
    first = resume.text_hash()
    resume.save_text("# Jordan Avery\n\nEdited again.")
    assert resume.text_hash() != first
