"""The two rules that code enforces, whatever the model decides (spec: Phase 2, Guardrails;
What it answers, drafts or leaves for you).

1. The agent never clicks a button that submits or applies. Every click the agent makes goes
   through `safe_click`, which refuses submit-type buttons and anything labeled Submit,
   Apply, Send application and the like. You click Submit yourself.
2. Demographic and EEO questions, legal attestations and consent boxes are never answered.
"""

import re

SUBMIT_WORDS = re.compile(
    r"\b(submit|apply|send|finish|complete|confirm|review and submit|place)\b"
    r"|\bsend application\b|\bi agree\b|\baccept\b", re.I)

SENSITIVE = re.compile(
    r"\b(race|racial|ethnic\w*|hispanic|latin[oax]|gender|sex|sexual orientation|lgbt\w*|pronoun\w*|"
    r"transgender|veteran|armed forces|military status|disabilit\w*|self[- ]identif\w*|voluntary|eeo\w*|"
    r"equal employment|date of birth|birth ?date|age range|marital|religio\w*|national origin|citizenship status)\b",
    re.I)

ATTESTATION = re.compile(
    r"\b(i certify|i attest|i acknowledge|i agree|i consent|i understand|i affirm|i declare|"
    r"acknowledg\w*|attest\w*|certif(y|ication)|consent|privacy (policy|notice)|terms|signature|"
    r"sign(ed)? (here|below)|e-?sign\w*|true and (complete|accurate)|background check authoriz\w*)\b",
    re.I)


class SubmitBlocked(Exception):
    """The agent tried to click something that could submit the application."""


def looks_like_submit(text: str, element_type: str = "", tag: str = "") -> bool:
    """True for anything that could send the application: a submit-type control, or a button
    or link whose text says submit, apply, send and so on."""
    if (element_type or "").lower() in ("submit", "image"):
        return True
    return bool(SUBMIT_WORDS.search(text or "")) and (tag or "").lower() in ("", "button", "a", "input")


def describe(locator) -> tuple[str, str, str]:
    """Text, type and tag of a Playwright locator's element, for the checks above."""
    return locator.evaluate(
        "el => [(el.innerText || el.value || el.getAttribute('aria-label') || '').trim(), "
        "(el.getAttribute('type') || '').toLowerCase(), el.tagName.toLowerCase()]")


# While the agent clicks, any form submission that click causes is cancelled (a <button>
# with no type submits its form by default). Your own clicks aren't affected.
ARM = """() => {
  if (!window.__jaGuard) {
    window.__jaGuard = true;
    document.addEventListener('submit', e => {
      if (window.__jaAgentClick) { e.preventDefault(); e.stopImmediatePropagation(); window.__jaBlockedSubmits = (window.__jaBlockedSubmits || 0) + 1; }
    }, true);
  }
  window.__jaAgentClick = true;
}"""
DISARM = "() => { window.__jaAgentClick = false; }"


def safe_click(locator) -> None:
    """The only way the agent clicks. Refuses anything that looks like Submit, and cancels
    any form submission the click would cause."""
    text, element_type, tag = describe(locator)
    if looks_like_submit(text, element_type, tag):
        raise SubmitBlocked(f"Blocked a click on “{text or element_type}”: the agent never submits.")
    page = locator.page
    page.evaluate(ARM)
    try:
        locator.click()
        page.wait_for_timeout(50)  # let the click's events run while armed
    finally:
        try:
            page.evaluate(DISARM)
        except Exception:  # noqa: BLE001 - the click navigated away; nothing left to disarm
            pass


def safe_press(locator, key: str) -> None:
    """A key press with submitting blocked, for search boxes that list options on Enter."""
    page = locator.page
    page.evaluate(ARM)
    try:
        locator.press(key)
        page.wait_for_timeout(50)
    finally:
        try:
            page.evaluate(DISARM)
        except Exception:  # noqa: BLE001
            pass


def is_sensitive(label: str) -> bool:
    """Demographic and EEO questions: never answered by the agent."""
    return bool(SENSITIVE.search(label or ""))


def is_attestation(label: str) -> bool:
    """Legal attestations, certifications and consent boxes: always left for you."""
    return bool(ATTESTATION.search(label or ""))
