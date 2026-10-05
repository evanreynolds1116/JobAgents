"""Fill a page from the mapping decisions (spec: How it works, steps 4 and 5).

Text is typed with `fill` (never Enter, which could submit a form). Choices are picked
from the field's own options, and every click goes through guard.safe_click. Fields to
check and fields left for you are outlined in the browser.
"""

from pathlib import Path

from apply import guard
from apply.extract import Field
from apply.mapping import Decision, best_option

REVIEW_COLOR = "#B26B00"    # amber: filled, please check
NEEDS_YOU_COLOR = "#A3261C"  # red: required and left blank


def _control(page, key: str):
    return page.locator(f'[data-ja-key="{key}"]')


def _check(locator) -> None:
    text, element_type, tag = guard.describe(locator)
    if guard.looks_like_submit(text, element_type, tag) and element_type not in ("radio", "checkbox"):
        raise guard.SubmitBlocked(f"Blocked “{text}”: the agent never submits.")
    locator.check(force=True)  # custom-styled radios hide the real input


def _pick_combobox(page, key: str, value: str) -> bool:
    """Type into a searchable dropdown and click the matching option."""
    box = _control(page, key)
    guard.safe_click(box)
    box.press_sequentially(value[:40], delay=15)
    try:
        page.locator('[role="option"]').first.wait_for(state="visible", timeout=4000)
    except Exception:  # noqa: BLE001 - no options appeared for what was typed
        box.press("Escape")
        return False
    options = page.locator('[role="option"]')
    texts = [t.strip() for t in options.all_inner_texts()]
    choice = best_option(value, texts) or (texts[0] if len(texts) == 1 else None)
    if choice is None:
        box.press("Control+A")
        box.press("Backspace")
        box.press("Escape")
        return False
    guard.safe_click(options.nth(texts.index(choice)))
    return True


def fill_field(page, f: Field, d: Decision, files: dict[str, Path | None]) -> bool:
    """Enter one decision. Returns False if the page wouldn't take it."""
    control = _control(page, f.key)
    if d.action in ("upload_resume", "upload_cover_letter"):
        path = files.get("resume" if d.action == "upload_resume" else "cover_letter")
        if not path:
            return False
        control.set_input_files(str(path))
        return True
    if d.action != "fill":
        return False
    values = d.value if isinstance(d.value, list) else [d.value]
    if f.kind == "select":
        control.select_option(label=values if f.multiple else values[0])
    elif f.kind in ("radio", "checkbox_group"):
        for v in values:
            _check(control.nth(f.options.index(v)))
    elif f.kind == "buttons":
        guard.safe_click(control.nth(f.options.index(values[0])))
    elif f.kind == "combobox":
        return all(_pick_combobox(page, f.key, v) for v in values)
    else:
        control.fill(values[0])
    return True


def highlight(page, key: str, color: str) -> None:
    page.evaluate(
        """([key, color]) => document.querySelectorAll(`[data-ja-key="${key}"]`).forEach(el => {
             const target = el.closest('[class*="control"]') || (el.type === 'radio' || el.type === 'checkbox'
                            ? el.closest('fieldset, li, div') : el);
             (target || el).style.outline = `3px solid ${color}`;
             (target || el).style.outlineOffset = '2px';
           })""", [key, color])


def fill_page(page, fields: list[Field], decisions: list[Decision], files: dict[str, Path | None]) -> list[Decision]:
    """Fill everything that has an answer, then set each decision's status and outline the
    fields that need a look. Returns the decisions with their status."""
    by_key = {f.key: f for f in fields}
    for d in decisions:
        f = by_key[d.key]
        if d.action == "leave":
            d.status = d.status or "needs_you"
        else:
            try:
                ok = fill_field(page, f, d, files)
            except guard.SubmitBlocked:
                raise
            except Exception:  # noqa: BLE001 - the page refused this one; leave it for you
                ok = False
            if not ok:
                d.action, d.status = "leave", "needs_you"
                d.note = d.note or "The form wouldn't take the answer"
            else:
                d.status = "filled" if d.confident else "review"
        if d.status == "review":
            highlight(page, d.key, REVIEW_COLOR)
        elif d.status == "needs_you" and f.required:
            highlight(page, d.key, NEEDS_YOU_COLOR)
    return decisions
