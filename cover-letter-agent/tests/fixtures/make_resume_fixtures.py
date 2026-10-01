r"""Regenerate the made-up resume PDFs used by tests/test_resume.py.

Needs fpdf2, which is a one-off tool and not in requirements.txt:
    .venv\Scripts\python -m pip install fpdf2
    .venv\Scripts\python tests\fixtures\make_resume_fixtures.py
"""

from pathlib import Path

from fpdf import FPDF

HERE = Path(__file__).resolve().parent
FONT = HERE.parents[1] / "static" / "fonts" / "PublicSans-Variable.ttf"

NAME = "Jordan Avery"
CONTACT = "jordan.avery@example.com · (555) 555-0142 · Nashville, TN · linkedin.com/in/jordanavery-example"
SUMMARY = (
    "Marketing coordinator with five years of experience running social media and "
    "events for community sports organizations."
)
EXPERIENCE = [
    ("Social Media Manager, Riverbend Youth Soccer League", "2021 – Present", [
        "Grew Instagram following from 2,400 to 9,100 in two seasons.",
        "Planned and ran a 40-team spring tournament with 600 attendees.",
        "Cut paid ad spend by 38% by shifting budget to player-made video.",
    ]),
    ("Marketing Assistant, Harpeth Valley Rec Center", "2019 – 2021", [
        "Wrote the weekly member newsletter for 3,000 subscribers.",
        "Coordinated volunteer schedules for 25 community events a year.",
    ]),
]
EDUCATION = ["B.A. Communication, Middle Tennessee State University, 2019"]
SKILLS = ["Canva and Adobe Express", "Hootsuite", "Google Analytics", "Event planning"]


def new_pdf() -> FPDF:
    pdf = FPDF(format="Letter")
    pdf.add_font("PublicSans", "", str(FONT))
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()
    return pdf


def text(pdf, x, w, size, line, gap=1.5):
    pdf.set_font("PublicSans", size=size)
    pdf.set_x(x)
    pdf.multi_cell(w, size * 0.5, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(gap)


def heading(pdf, x, w, label):
    pdf.ln(3)
    text(pdf, x, w, 13, label.upper(), gap=1)


def experience(pdf, x, w):
    heading(pdf, x, w, "Experience")
    for title, dates, bullets in EXPERIENCE:
        text(pdf, x, w, 10, f"{title} ({dates})")
        for b in bullets:
            text(pdf, x + 3, w - 3, 10, f"• {b}", gap=0.5)


def one_column():
    pdf = new_pdf()
    x, w = pdf.l_margin, pdf.epw
    text(pdf, x, w, 22, NAME)
    text(pdf, x, w, 10, CONTACT)
    heading(pdf, x, w, "Summary")
    text(pdf, x, w, 10, SUMMARY)
    experience(pdf, x, w)
    heading(pdf, x, w, "Education")
    for e in EDUCATION:
        text(pdf, x, w, 10, e)
    heading(pdf, x, w, "Skills")
    for s in SKILLS:
        text(pdf, x, w, 10, f"• {s}", gap=0.5)
    pdf.output(str(HERE / "resume_one_column.pdf"))


def two_column():
    """Full-width name and contact line, then a skills sidebar beside the main column."""
    pdf = new_pdf()
    full_x, full_w = pdf.l_margin, pdf.epw
    text(pdf, full_x, full_w, 22, NAME)
    text(pdf, full_x, full_w, 10, CONTACT)
    top = pdf.get_y() + 4

    side_x, side_w = full_x, 50
    pdf.set_y(top)
    heading(pdf, side_x, side_w, "Skills")
    for s in SKILLS:
        text(pdf, side_x, side_w, 10, f"• {s}", gap=0.5)
    heading(pdf, side_x, side_w, "Education")
    for e in EDUCATION:
        text(pdf, side_x, side_w, 10, e)

    main_x = full_x + side_w + 12
    main_w = full_w - side_w - 12
    pdf.set_y(top)
    heading(pdf, main_x, main_w, "Summary")
    text(pdf, main_x, main_w, 10, SUMMARY)
    experience(pdf, main_x, main_w)
    pdf.output(str(HERE / "resume_two_column.pdf"))


if __name__ == "__main__":
    one_column()
    two_column()
    print("Wrote resume_one_column.pdf and resume_two_column.pdf")
