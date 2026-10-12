"""Resume storage and conversion: an uploaded PDF or .docx becomes data/resume.md.

The conversion aims to keep every word and the section structure; you review and
correct the result in the Profile screen. The original file is kept for reference
(and, in Phase 2, for uploading to application forms).
"""

import hashlib
import io
import re
import shutil
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

import config

ORIGINAL_STEM = "resume_original"
SUPPORTED = (".pdf", ".docx")
BULLET_CHARS = "•●▪■◦○‣∙·*–-"
BULLET_RE = re.compile(rf"^\s*[{re.escape(BULLET_CHARS)}]\s+")


class ConversionError(Exception):
    """The file couldn't be turned into text; the message is shown to the user."""


# --- Storage ---------------------------------------------------------------


def resume_path() -> Path:
    return config.DATA_DIR / "resume.md"


def load_text() -> str:
    path = resume_path()
    return path.read_text(encoding="utf-8") if path.exists() else ""


def save_text(text: str) -> None:
    _write_atomic(resume_path(), text.strip() + "\n" if text.strip() else "")


def has_resume() -> bool:
    return bool(load_text().strip())


def text_hash(text: str | None = None) -> str:
    """Short hash of the resume text, recorded on each draft (spec: Data & storage)."""
    text = load_text() if text is None else text
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def original_file() -> Path | None:
    for suffix in SUPPORTED:
        path = config.DATA_DIR / f"{ORIGINAL_STEM}{suffix}"
        if path.exists():
            return path
    return None


def upload_name(name: str, suffix: str) -> str:
    """The file name employers see on application forms: "Evan Reynolds" -> "EvanReynoldsResume.pdf"."""
    words = [re.sub(r"[^A-Za-z0-9]", "", w) for w in name.split()]
    return "".join(w for w in words if w) + "Resume" + suffix


def upload_file(name: str) -> Path | None:
    """A copy of the original named for uploading to forms (data/upload/), refreshed each time,
    so a replaced resume is never sent under an old copy. Kept on this computer only."""
    original = original_file()
    if original is None:
        return None
    folder = config.LOCAL_DIR / "upload"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*Resume.*"):
        old.unlink()
    target = folder / upload_name(name, original.suffix)
    shutil.copyfile(original, target)
    return target


def original_info() -> tuple[str, datetime] | None:
    """(file name, upload time) of the stored original, if any."""
    path = original_file()
    if path is None:
        return None
    return path.name, datetime.fromtimestamp(path.stat().st_mtime)


def import_file(filename: str, data: bytes) -> str:
    """Convert an uploaded resume, store the original and resume.md, and return the text."""
    suffix = Path(filename).suffix.lower()
    text = convert(filename, data)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for old in SUPPORTED:  # only one original at a time
        (config.DATA_DIR / f"{ORIGINAL_STEM}{old}").unlink(missing_ok=True)
    (config.DATA_DIR / f"{ORIGINAL_STEM}{suffix}").write_bytes(data)
    save_text(text)
    return text


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


# --- Conversion ------------------------------------------------------------


def convert(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        text = pdf_to_markdown(data)
    elif suffix == ".docx":
        text = docx_to_markdown(data)
    else:
        raise ConversionError("Upload a PDF or a .docx file.")
    if len(re.sub(r"\W", "", text)) < 50:
        raise ConversionError(
            "Couldn't find any text in this file. If it's a scanned PDF, upload the "
            ".docx version instead, or paste your resume into the text box."
        )
    return text


def _tidy(lines: list[str]) -> str:
    """Join lines, collapsing runs of blank lines."""
    text = "\n".join(line.rstrip() for line in lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def _bullet(text: str) -> str | None:
    if BULLET_RE.match(text):
        return "- " + BULLET_RE.sub("", text, count=1).strip()
    return None


def _looks_like_heading(text: str) -> bool:
    """Short all-caps lines such as EXPERIENCE or SKILLS & TOOLS."""
    letters = [c for c in text if c.isalpha()]
    return 3 <= len(letters) <= 40 and all(c.isupper() for c in letters) and len(text.split()) <= 5


# PDF -----------------------------------------------------------------------


def pdf_to_markdown(data: bytes) -> str:
    import pdfplumber

    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as exc:  # pdfminer raises a variety of errors on bad files
        raise ConversionError("This PDF couldn't be opened. Is it password-protected or damaged?") from exc

    with pdf:
        lines = []  # (text, size, gap_before) in reading order
        for page in pdf.pages:
            for region in _reading_regions(page):
                lines.extend(_region_lines(region))
                lines.append(None)  # region break
    sizes = Counter()  # font size -> characters set in it
    for item in lines:
        if item:
            sizes[item[1]] += len(item[0])
    if not sizes:
        return ""
    body = sizes.most_common(1)[0][0]
    largest = max(item[1] for item in lines if item)

    out: list[str] = []
    name_done = False
    for item in lines:
        if item is None:
            out.append("")
            continue
        text, size, big_gap = item
        if big_gap:
            out.append("")
        if not name_done and size == largest and size > body * 1.3:
            out.append(f"# {text}")
            name_done = True
        elif size >= body * 1.15 or _looks_like_heading(text):
            out.extend(["", f"## {text}", ""])
        else:
            out.append(_bullet(text) or text)
    return _tidy(out)


def _reading_regions(page):
    """Split a page into a full-width header plus left and right columns when it has two.

    A row of text "spans" a candidate gutter if a word crosses it or the text flows
    across it with only a normal word space. Spanning rows are only allowed at the
    top (name, contact line); below them the two sides must never touch.
    """
    words = page.extract_words()
    if len(words) < 20:
        return [page]
    rows: dict[int, list] = {}
    for w in words:
        rows.setdefault(round(w["top"] / 3), []).append(w)

    width = float(page.width)
    candidates = []  # (header_bottom, x)
    for x in range(int(width * 0.2), int(width * 0.8), 2):
        header_bottom = 0.0
        for row in rows.values():
            left = [w["x1"] for w in row if w["x1"] <= x]
            right = [w["x0"] for w in row if w["x0"] >= x]
            crossing = any(w["x0"] < x < w["x1"] for w in row)
            if crossing or (left and right and min(right) - max(left) < 10):
                header_bottom = max(header_bottom, max(w["bottom"] for w in row))
        below = [w for w in words if w["top"] > header_bottom]
        if len(below) < len(words) * 0.6:
            continue
        n_left = sum(1 for w in below if w["x1"] <= x)
        if min(n_left, len(below) - n_left) < len(below) * 0.15:
            continue
        candidates.append((header_bottom, x))
    if not candidates:
        return [page]
    header_bottom = min(c[0] for c in candidates)
    gutter = [x for hb, x in candidates if hb == header_bottom]
    x = gutter[len(gutter) // 2]  # middle of the gap

    regions = []
    if header_bottom:
        regions.append(page.crop((0, 0, width, header_bottom + 1)))
    top = header_bottom + 1 if header_bottom else 0
    regions.append(page.crop((0, top, x, page.height)))
    regions.append(page.crop((x, top, width, page.height)))
    return regions


def _region_lines(region):
    result = []
    prev_bottom = None
    prev_height = None
    for line in region.extract_text_lines(strip=True, return_chars=True):
        text = line["text"].strip()
        if not text:
            continue
        chars = [c for c in line["chars"] if c["text"].strip()]
        size = statistics.median(c["size"] for c in chars) if chars else 0
        height = line["bottom"] - line["top"]
        gap = prev_bottom is not None and (line["top"] - prev_bottom) > max(prev_height or 0, height) * 0.9
        result.append((text, round(size, 1), gap))
        prev_bottom, prev_height = line["bottom"], height
    return result


# DOCX ----------------------------------------------------------------------

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def docx_to_markdown(data: bytes) -> str:
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # bad zip, missing parts, wrong content type
        raise ConversionError("This .docx file couldn't be opened. Is it damaged?") from exc

    out: list[str] = []
    seen: set[str] = set()

    # Contact details often live in the page header.
    for section in document.sections:
        for block in section.header.iter_inner_content():
            _docx_block(block, out, seen)
    _docx_container(document, out, seen)
    for section in document.sections:
        for block in section.footer.iter_inner_content():
            _docx_block(block, out, seen)
    return _tidy(out)


def _docx_container(container, out, seen) -> None:
    for block in container.iter_inner_content():
        _docx_block(block, out, seen)


def _docx_block(block, out, seen) -> None:
    from docx.table import Table

    if isinstance(block, Table):
        done_cells = set()
        for row in block.rows:
            for cell in row.cells:
                if id(cell._tc) in done_cells:  # merged cells repeat
                    continue
                done_cells.add(id(cell._tc))
                _docx_container(cell, out, seen)
            out.append("")
    else:
        _docx_paragraph(block, out, seen)


def _docx_paragraph(paragraph, out, seen) -> None:
    from docx.text.paragraph import Paragraph

    # Text boxes (common in resume templates) sit inside runs and aren't part of
    # paragraph.text. Skip mc:Fallback copies so each box is read once.
    for txbx in paragraph._p.iter(f"{{{W_NS}}}txbxContent"):
        if any(True for _ in txbx.iterancestors(f"{{{MC_NS}}}Fallback")):
            continue
        for p in txbx.iter(f"{{{W_NS}}}p"):
            _docx_paragraph(Paragraph(p, paragraph._parent), out, seen)

    text = _docx_paragraph_text(paragraph).strip()
    if not text:
        out.append("")
        return
    style = (paragraph.style.name if paragraph.style is not None else "") or ""
    level = None
    if style == "Title":
        level = 1
    elif style.startswith("Heading"):
        digits = style.removeprefix("Heading").strip()
        level = min(int(digits) + 1, 4) if digits.isdigit() else 2
    elif _looks_like_heading(text):
        level = 2

    if level:
        out.extend(["", f"{'#' * level} {text}", ""])
    elif _is_list_paragraph(paragraph, style):
        out.append(_bullet(text) or f"- {text}")
    elif _all_bold(paragraph):
        out.append(f"**{text}**")
    else:
        out.append(_bullet(text) or text)


def _docx_paragraph_text(paragraph) -> str:
    from docx.text.hyperlink import Hyperlink

    parts = []
    for item in paragraph.iter_inner_content():
        if isinstance(item, Hyperlink):
            label, url = item.text.strip(), (item.address or "").strip()
            if url and label and url.rstrip("/") not in label and not url.startswith("mailto:"):
                parts.append(f"[{label}]({url})")
            else:
                parts.append(item.text)
        else:
            parts.append(item.text)
    return "".join(parts)


def _is_list_paragraph(paragraph, style: str) -> bool:
    if "List" in style:
        return True
    ppr = paragraph._p.pPr
    return ppr is not None and ppr.numPr is not None


def _all_bold(paragraph) -> bool:
    runs = [r for r in paragraph.runs if r.text.strip()]
    return bool(runs) and all(r.bold for r in runs) and len(paragraph.text) <= 80
