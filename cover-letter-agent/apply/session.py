"""One form-filling session (spec: Phase 2, How it works).

Playwright must be driven from the thread that started it, while Streamlit reruns the
screen on other threads. So each session runs in its own worker thread and the Fill
application screen sends it commands (confirm, resume, continue, stop, close) and reads a
snapshot of where it is. One session at a time.

Steps: open the link and find the form -> wait for you to confirm it -> pause if the site
needs a login or shows a CAPTCHA -> read and map the page, draft screening answers, and
pause if the form requires a cover letter you don't have -> fill -> wait for you to review
and continue -> save every field's final value and offer to save answers you typed -> next
page, or stop on the last one and hand over. The browser stays open so you can submit; the
agent never does.
"""

import copy
import queue
import re
import threading
from collections.abc import Callable
from pathlib import Path

import config
from apply import extract, fill, guard, resolve
from apply.mapping import SALARY, Decision
from storage import filled

PROFILE_DIR_NAME = "browser_profile"
WAIT_STEP_MS = 300
NEXT_WORDS = re.compile(r"^\s*(next|continue|save (and|&) continue|next step|proceed)\b", re.I)
COVER_LETTER = re.compile(r"cover letter|motivation letter|letter of interest", re.I)
NOT_WORTH_SAVING = re.compile(r"\b(name|e-?mail|phone|linkedin|github|website|url|portfolio|address|city|zip|"
                              r"postal|resume|cv|cover letter)\b", re.I)

PAGE_TITLE = r"""
() => {
  const pick = s => [...document.querySelectorAll(s)].find(e => e.offsetParent && e.innerText.trim());
  const el = pick('[data-automation-id="pageHeader"]') || pick('main h2, form h2') || pick('h2') || pick('h1');
  return el ? el.innerText.trim().replace(/\s+/g, ' ').slice(0, 60) : '';
}
"""
ERRORS = r"""
() => [...document.querySelectorAll('[role="alert"], [data-automation-id="errorMessage"], [class*="error-message"], [aria-invalid="true"]')]
        .filter(e => e.offsetParent).map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 3).join(' ')
"""

CHECK_PAGE = r"""
() => {
  const visible = el => !!(el.offsetParent || el.getClientRects().length);
  if ([...document.querySelectorAll('input[type=password]')].some(visible)) return 'login';
  const challenge = [...document.querySelectorAll('iframe')].some(f => {
    const r = f.getBoundingClientRect();
    return /captcha|challenge|turnstile/i.test((f.src || '') + (f.title || '')) && r.width >= 250 && r.height >= 150;
  });
  if (challenge || /verify (that )?you are (a )?human|are you a robot|security check/i.test(document.body.innerText.slice(0, 3000)))
    return 'captcha';
  return '';
}
"""


def launch_browser(playwright, headless: bool = False):
    """Your installed Chrome, with the app's own profile so job-site logins persist."""
    profile = config.DATA_DIR / PROFILE_DIR_NAME
    profile.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(str(profile), channel="chrome", headless=headless,
                                                         no_viewport=True)


class Closed(Exception):
    """The browser window was closed or the session was stopped."""


class Session:
    def __init__(self, app_id: int, url: str, mapper: Callable, files: dict[str, Path | None],
                 launcher: Callable = launch_browser, headless: bool = False, setup: Callable | None = None,
                 drafter: Callable | None = None, after_fill: Callable | None = None, has_letter: bool = True):
        self.app_id, self.url, self.mapper, self.files = app_id, url, mapper, files
        self.launcher, self.headless, self.setup = launcher, headless, setup
        self.drafter, self.after_fill, self.has_letter = drafter, after_fill, has_letter
        self._commands: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._state = {"state": "starting", "message": "Opening the browser…", "url": url, "platform": "",
                       "steps": [], "page": 1, "rows": [], "pages_done": [], "error": "", "offers": [],
                       "titles": {}}
        self.thread = threading.Thread(target=self._run, name=f"fill-{app_id}", daemon=True)

    # Talking to the screen ------------------------------------------------------------

    def start(self) -> "Session":
        self.thread.start()
        return self

    def send(self, command: str) -> None:
        self._commands.put(command)

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._state)

    @property
    def active(self) -> bool:
        return self.thread.is_alive()

    def _set(self, **changes) -> None:
        with self._lock:
            self._state.update(changes)

    # The worker ---------------------------------------------------------------------

    def _wait(self, page, *allowed: str) -> str:
        """Wait for one of `allowed` commands, keeping the browser responsive."""
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                try:
                    page.wait_for_timeout(WAIT_STEP_MS)
                except Exception as exc:  # noqa: BLE001 - the window was closed
                    raise Closed() from exc
                continue
            if command == "close":
                raise Closed()
            if command in allowed:
                return command

    def _run(self) -> None:
        from playwright.sync_api import sync_playwright

        context = None
        try:
            with sync_playwright() as p:
                context = self.launcher(p, headless=self.headless)
                if self.setup:
                    self.setup(context)  # tests serve fixture pages here
                blocked: list[str] = []
                resolve.block_job_boards(context, blocked)
                page = context.pages[0] if context.pages else context.new_page()
                self._set(state="finding", message="Finding the application form…")
                found = resolve.resolve(page, self.url, blocked)
                self._set(url=found.url, platform=found.platform_name, steps=found.steps)
                if not found.ok:
                    self._set(state="blocked", message=found.reason)
                    self._wait(page)  # until closed
                self._set(state="confirm", message=f"Found {found.platform_name} at {found.url}. Check that it's "
                                                   "the right job, then confirm.")
                if self._wait(page, "confirm", "stop") == "stop":
                    self._stopped(page)
                self._fill_pages(page)
        except Closed:
            self._set(state="closed", message="The browser was closed.")
        except guard.SubmitBlocked as exc:
            self._set(state="error", error=str(exc), message="Stopped: the agent was about to click a submit button.")
        except Exception as exc:  # noqa: BLE001 - show the problem on the screen instead of dying silently
            self._set(state="error", error=f"{type(exc).__name__}: {exc}", message="Filling stopped with an error.")
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:  # noqa: BLE001
                    pass

    def _stopped(self, page) -> None:
        self._set(state="stopped", message="Stopped. The browser stays open; nothing was submitted.")
        self._wait(page)

    def _fill_pages(self, page) -> None:
        page_no = 1
        while True:
            self._set(page=page_no)
            final = self._clear_the_way(page)
            title = _title(page)
            with self._lock:
                self._state["titles"][str(page_no)] = title
            label = f"page {page_no}" + (f" ({title})" if title else "")
            if final:
                self._set(state="done", rows=[], message="You're on the final review page. Check everything in the "
                          "browser and submit it yourself when you're ready. Then mark the application as submitted.")
                self._wait(page)  # keep the window open until you close it
            self._set(state="filling", message=f"Reading {label} and working out the answers…")
            fields = extract.read_fields(page)
            decisions = self.mapper(fields)
            if self.drafter:
                self._set(message="Drafting answers to the screening questions…")
                decisions = self.drafter(fields, decisions)
            if not self.has_letter and any(f.required and COVER_LETTER.search(f.label) for f in fields):
                self._set(state="needs_letter",
                          message="This form requires a cover letter, and this application doesn't have an approved "
                                  "one. Draft one with the cover letter agent, or fill the rest and leave the letter "
                                  "for you.")
                if self._wait(page, "skip_letter", "stop") == "stop":
                    self._stopped(page)
            self._set(state="filling", message=f"Filling {label}…")
            decisions = fill.fill_page(page, fields, decisions, self.files)
            if self.after_fill:
                self.after_fill(fields, decisions)
            by_key = {f.key: f for f in fields}
            self._set(state="review", rows=[_row(by_key[d.key], d) for d in decisions],
                      message=f"Paused on {label}. Check the fields in the browser window and fix anything "
                              "there, then continue. The agent never clicks Submit.")
            while True:  # until the form moves on, or this is the last page
                if self._wait(page, "continue", "stop") == "stop":
                    self._stopped(page)
                self._set(state="filling", message="Saving this page's answers and moving on…")
                self._save_final(page, page_no, fields, decisions)
                following = _next_button(page)
                if following is None:
                    self._set(state="done", message="All filled. Review the form in the browser and submit it "
                                                    "yourself when you're ready. Then mark the application as "
                                                    "submitted.")
                    self._wait(page)  # keep the window open until you close it
                before = _signature(page)
                guard.safe_click(following)
                if _moved_on(page, before):
                    break
                problem = page.evaluate(ERRORS)
                self._set(state="review", message="The form didn't move on to the next page"
                          + (f": “{problem[:160]}”" if problem else "") + ". Fix what it flags in the browser, then "
                          "continue.")
            page_no += 1

    def _clear_the_way(self, page) -> bool:
        """Pause for a login, a CAPTCHA, or a page with nothing to fill yet (for example
        Workday's sign-in and its Start Your Application choices). Returns True on a final
        review page: nothing to fill, no Next, and a Submit button for you."""
        while True:
            problem = page.evaluate(CHECK_PAGE)
            if not problem and (extract.read_fields(page, open_dropdowns=False) or _next_button(page)):
                return False
            if not problem and _submit_button(page):
                return True
            if problem == "login":
                message = "The site wants you to log in or create an account. Do it in the browser window, then click Resume."
            elif problem == "captcha":
                message = "The site wants you to complete a check. Do it in the browser window, then click Resume."
            else:
                message = ("There's nothing to fill on this page yet. Open the application form in the browser (for "
                           "example, click Apply Manually), then click Resume.")
            self._set(state="login", message=message)
            if self._wait(page, "resume", "stop") == "stop":
                self._stopped(page)

    def _save_final(self, page, page_no: int, fields, decisions: list[Decision]) -> None:
        """Every field's final value, including your edits, on the application's record."""
        now = {f.label: f.value for f in extract.read_fields(page, open_dropdowns=False)}
        rows = []
        for f, d in zip(fields, decisions):
            value = now.get(f.label, f.value)
            entered = d.value if d.action != "leave" else ""
            changed = bool(value) and _plain(value) != _plain(entered) and d.action not in ("upload_resume",
                                                                                          "upload_cover_letter")
            source = "you" if changed else (d.source if value else "none")
            status = "you" if changed else (d.status if value or d.status == "left_for_you" else "needs_you")
            rows.append({"label": f.label, "value": value, "source": source, "status": status})
        filled.save_page(self.app_id, page_no, rows)
        offers = [{"label": f.label, "value": row["value"]} for f, row in zip(fields, rows)
                  if row["source"] == "you" and worth_saving(f, row["value"])]
        with self._lock:
            self._state["pages_done"].append(page_no)
            self._state["offers"].extend(offers)


def worth_saving(f, value) -> bool:
    """An answer you typed that later applications could reuse: a real question, not contact
    details, files, salary or anything the agent never answers."""
    return (bool(value) and isinstance(value, str) and f.kind in ("text", "textarea", "select", "radio", "buttons",
                                                                    "combobox")
            and not NOT_WORTH_SAVING.search(f.label) and not SALARY.search(f.label)
            and not guard.is_sensitive(f.label) and not guard.is_attestation(f.label))


def _plain(value) -> str:
    if isinstance(value, list):
        value = " | ".join(sorted(value))
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def _row(f, d: Decision) -> dict:
    shown = d.value if not isinstance(d.value, list) else ", ".join(d.value)
    if d.source == "cover_letter" and d.action == "fill":
        shown = f"Approved letter, {len(str(d.value).split())} words"
    elif d.source == "drafted":
        shown = f"Draft, {len(str(d.value).split())} words (highlighted in the browser)"
    return {"label": f.label, "kind": f.kind, "required": f.required, "value": shown, "source": d.source,
            "status": d.status, "note": d.note}


def _title(page) -> str:
    try:
        return page.evaluate(PAGE_TITLE)
    except Exception:  # noqa: BLE001
        return ""


def _signature(page) -> str:
    """What's on the page: its title and field labels, to tell whether Next moved on."""
    try:
        labels = [f.label for f in extract.read_fields(page, open_dropdowns=False)]
    except Exception:  # noqa: BLE001
        labels = []
    return _title(page) + "|" + "|".join(labels) + "|" + page.url


def _moved_on(page, before: str, timeout_ms: int = 8000) -> bool:
    """Wait for the next page (a new address, or a single-page app swapping its content)."""
    waited = 0
    while waited < timeout_ms:
        page.wait_for_timeout(400)
        waited += 400
        try:
            page.wait_for_load_state("domcontentloaded", timeout=2000)
        except Exception:  # noqa: BLE001
            pass
        if _signature(page) != before:
            page.wait_for_timeout(600)  # let the new page finish drawing
            return True
        if page.evaluate(ERRORS):
            return False
    return False


def _submit_button(page) -> bool:
    """A visible button that would submit: only ever looked at, never clicked."""
    buttons = page.locator("button, input[type=submit], input[type=button]")
    for i in range(buttons.count()):
        b = buttons.nth(i)
        try:
            if b.is_visible() and guard.looks_like_submit(*guard.describe(b)):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _next_button(page):
    """A Next or Continue button for a multi-page form; never one that submits."""
    buttons = page.locator("button, input[type=button], a[role=button]")
    for i in range(buttons.count()):
        b = buttons.nth(i)
        try:
            if not b.is_visible():
                continue
            text, element_type, tag = guard.describe(b)
        except Exception:  # noqa: BLE001
            continue
        if NEXT_WORDS.search(text) and not guard.looks_like_submit(text, element_type, tag):
            return b
    return None


# One session at a time --------------------------------------------------------------

_current: Session | None = None
_current_lock = threading.Lock()


def current() -> Session | None:
    return _current


def start(session: Session) -> Session:
    global _current
    with _current_lock:
        if _current and _current.active:
            raise RuntimeError("Another application is being filled. Close its browser window first.")
        _current = session.start()
        return _current
