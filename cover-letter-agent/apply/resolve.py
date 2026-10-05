"""Find the real application form from a job link (spec: Phase 2, Finding the real
application form).

1. Open the link and let redirects happen (an Adzuna link passes through Adzuna first).
   Navigation to job boards whose terms forbid automated reading (LinkedIn, Indeed and so
   on) is blocked before the page loads, and you're asked for the company's own link.
2. If the page is a posting rather than the form, follow its Apply link, or open an
   embedded Greenhouse form directly. Links are opened by their address, never clicked,
   so an Apply *button* that would submit something is never pressed.
3. Report the final address, the platform and how it got there, for you to confirm.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from agent.fetch import NO_FETCH_DOMAINS, blocked_domain

PLATFORMS = (
    ("greenhouse", re.compile(r"(^|\.)greenhouse\.io$")),
    ("lever", re.compile(r"(^|\.)lever\.co$")),
    ("ashby", re.compile(r"(^|\.)ashbyhq\.com$")),
    ("workday", re.compile(r"myworkdayjobs\.com$|(^|\.)workday\.com$")),
    ("icims", re.compile(r"(^|\.)icims\.com$")),
    ("smartrecruiters", re.compile(r"(^|\.)smartrecruiters\.com$")),
)
PLATFORM_NAMES = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby", "workday": "Workday",
                  "icims": "iCIMS", "smartrecruiters": "SmartRecruiters", "other": "the company's own form"}
AGGREGATORS = ("adzuna.com",)  # listing pages that point to the employer's posting
MIN_FORM_FIELDS = 3


@dataclass
class Resolution:
    ok: bool
    url: str = ""
    platform: str = "other"
    steps: list[str] = field(default_factory=list)  # how it got here, for the Fill application screen
    reason: str = ""                                # why it stopped, when ok is False

    @property
    def platform_name(self) -> str:
        return PLATFORM_NAMES.get(self.platform, PLATFORM_NAMES["other"])


def platform_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return next((name for name, pattern in PLATFORMS if pattern.search(host)), "other")


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def block_job_boards(context, blocked: list[str]) -> None:
    """Stop page navigation to a no-fetch job board before it loads. Playwright routes see
    only the first request of a server redirect, so `resolve` also checks where each page
    ended up and stops there, without reading it."""
    def handler(route):
        request = route.request
        if request.is_navigation_request() and (domain := blocked_domain(request.url)):
            blocked.append(domain)
            route.abort("blockedbyclient")
        else:
            route.fallback()  # the next handler, or the network
    context.route("**/*", handler)


FORM_INFO = r"""
() => {
  const visible = el => !!(el.offsetParent || el.getClientRects().length);
  const fields = [...document.querySelectorAll('input, select, textarea')].filter(el =>
      !['hidden', 'submit', 'button', 'image', 'reset', 'search'].includes((el.type || '').toLowerCase()) &&
      (visible(el) || el.type === 'file'));
  const hasEmail = fields.some(el => el.type === 'email' || /e-?mail/i.test(el.name + ' ' + el.id + ' ' +
      (el.getAttribute('aria-label') || '') + ' ' + (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.innerText || '')));
  const iframe = [...document.querySelectorAll('iframe')].map(f => f.src)
      .find(s => /greenhouse\.io\/embed\/job_app|jobs\.lever\.co|jobs\.ashbyhq\.com/.test(s || ''));
  const links = [...document.querySelectorAll('a[href]')].map(a => ({text: a.innerText.trim(), href: a.href}))
      .filter(l => l.href && !l.href.startsWith('javascript:') && !l.href.endsWith('#'));
  return {count: fields.length, hasEmail, iframe: iframe || '', links};
}
"""


def _apply_link(links: list[dict], here: str) -> str | None:
    """The best Apply link on a posting page: an applicant tracking system's form first,
    then any link that says apply."""
    def says_apply(link):
        return re.search(r"\bapply\b|\bapplication\b", link["text"], re.I) or link["href"].rstrip("/").endswith("/apply")
    candidates = [link for link in links if says_apply(link) and link["href"] != here and not blocked_domain(link["href"])]
    ats = [link for link in candidates if platform_of(link["href"]) != "other"]
    return (ats or candidates or [{}])[0].get("href")


def _employer_link(links: list[dict], here: str) -> str | None:
    """On an aggregator's listing page, a link out to the employer's posting."""
    host = _host(here)
    outside = [link for link in links if _host(link["href"]) not in ("", host) and not blocked_domain(link["href"])
               and not _host(link["href"]).endswith(AGGREGATORS)]
    preferred = [link for link in outside if re.search(r"apply|original|company site|view (job|posting)", link["text"], re.I)]
    return (preferred or [{}])[0].get("href")


def resolve(page, url: str, blocked: list[str], max_hops: int = 4) -> Resolution:
    """Open `url` and find the application form. `blocked` collects job boards the
    navigation tried to reach (see block_job_boards)."""
    steps = [f"{_describe(url)} link"]
    if domain := blocked_domain(url):
        return Resolution(False, url, steps=steps, reason=_board_reason(domain))
    for _ in range(max_hops):
        try:
            answer = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if answer is not None and answer.status >= 400 and not blocked:
                return Resolution(False, page.url, steps=steps, reason=_refused_reason(page.url, answer.status))
            _settle(page, url)
        except Exception as exc:  # noqa: BLE001
            if blocked:
                return Resolution(False, url, steps=steps + [f"redirected to {blocked[-1]}"],
                                  reason=_board_reason(blocked[-1]))
            if "Timeout" not in type(exc).__name__:
                return Resolution(False, url, steps=steps, reason="The page couldn't be opened.")
        here = page.url
        if domain := blocked_domain(here) or (blocked[-1] if blocked else None):
            return Resolution(False, here, steps=steps + [f"redirected to {domain}"], reason=_board_reason(domain))
        if here.rstrip("/") != url.rstrip("/"):
            steps.append(f"redirect followed to {_short(here)}")
        info = page.evaluate(FORM_INFO)
        if info["count"] >= MIN_FORM_FIELDS and info["hasEmail"]:
            steps.append(f"{PLATFORM_NAMES.get(platform_of(here), 'Application')} form" if platform_of(here) != "other"
                         else "application form")
            return Resolution(True, here, platform_of(here), steps)
        if info["iframe"]:
            url = info["iframe"]
            steps.append("embedded application form")
            continue
        if _host(here).endswith(AGGREGATORS):
            url = _employer_link(info["links"], here)
            if not url:
                return Resolution(False, here, steps=steps,
                                  reason="This listing page doesn't link to the employer's posting without a login. "
                                         "Add the company's own link for this job.")
            steps.append(f"employer's posting at {_short(url)}")
            continue
        url = _apply_link(info["links"], here)
        if not url:
            return Resolution(False, here, steps=steps,
                              reason="Couldn't find the application form on this page. Open it in the browser "
                                     "and use its address, or add the company's own link.")
        steps.append("Apply link")
    return Resolution(False, page.url, steps=steps, reason="Couldn't reach an application form in a few steps.")


def _settle(page, started: str) -> None:
    """Give a page a moment to redirect itself (meta refresh or script), then to load."""
    try:
        page.wait_for_url(lambda u: u.rstrip("/") != started.rstrip("/"), timeout=1500)
    except Exception:  # noqa: BLE001 - it didn't redirect
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:  # noqa: BLE001 - some pages never go quiet; what's there is enough
        pass


def _refused_reason(url: str, status: int) -> str:
    """A site that turned the browser away. The agent doesn't try to get past that."""
    if status in (404, 410):
        return "The posting wasn't found. It may have closed. Add the company's own link if it's still open."
    site = "Adzuna" if _host(url).endswith("adzuna.com") else _host(url)
    return (f"{site} turned the app's browser away (HTTP {status}); it blocks automated browsers, and the agent "
            "doesn't try to get around that. Open the job in your own browser, follow it to the company's "
            "posting, and add that link below.")


def _board_reason(domain: str) -> str:
    return (f"This link leads to {domain}, which doesn't allow automated use, and the agent never fills forms "
            "hosted by job boards. Add the company's own link for this job.")


def _describe(url: str) -> str:
    host = _host(url)
    if host.endswith("adzuna.com"):
        return "Adzuna"
    if any(host == d or host.endswith("." + d) for d in NO_FETCH_DOMAINS):
        return host
    return {"other": "Job"}.get(platform_of(url), PLATFORM_NAMES[platform_of(url)])


def _short(url: str) -> str:
    parts = urlsplit(url)
    return f"{_host(url)}{parts.path}"[:80]
