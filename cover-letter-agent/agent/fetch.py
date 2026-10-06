"""Job fetcher: URL -> clean posting text, or a reason to ask you to paste it.

One request per URL you paste, made the way a browser visit would be. It never
logs in, retries around blocks or tries to get past bot protection; anything it
can't read falls back to pasting the text (spec: Edge cases & error handling).
The one exception: a careers page that builds itself with JavaScript but carries a
Greenhouse job ID (cribl.io/job-detail/6143413004, acme.com/careers?gh_jid=123) is
read from Greenhouse's public job API instead, at most two requests, and only when
that job points back to the same site.
"""

import json
import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
import trafilatura

MAX_CHARS = 30_000   # cap on posting text sent to Claude; you're warned if it's trimmed
MIN_CHARS = 400      # less than this is a login wall, an error page or a JavaScript shell
MAX_REDIRECTS = 5
TIMEOUT = 30.0     # some applicant tracking systems are slow (Greenhouse took 16 s in testing)
# Says what it is rather than imitating a browser; sites that refuse it get the paste fallback.
USER_AGENT = "Mozilla/5.0 (compatible; JobAssistant/0.1; personal job-application helper)"

# Sites whose terms don't allow automated reading, or that need a login to show
# a posting. The app skips the request and asks for the pasted text instead.
NO_FETCH_DOMAINS = ("linkedin.com", "indeed.com", "glassdoor.com", "jobright.ai", "hiring.cafe")

LOGIN_HINTS = ("sign in", "log in", "login", "create an account", "join now")
JS_HINTS = ("enable javascript", "javascript is required", "javascript is disabled", "unsupported browser")


@dataclass
class FetchResult:
    ok: bool
    url: str
    text: str = ""
    reason: str = ""           # shown to you when ok is False
    trimmed: bool = False
    hints: dict = field(default_factory=dict)  # title/company from the page's JobPosting data


def normalize_input_url(url: str) -> str:
    url = url.strip()
    if url and "://" not in url:
        url = "https://" + url
    return url


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def blocked_domain(url: str) -> str | None:
    host = _host(url)
    for domain in NO_FETCH_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return domain
    return None


# Job sites that list other companies' jobs: their address says nothing about the employer.
LISTING_SITES = NO_FETCH_DOMAINS + ("adzuna.com", "ziprecruiter.com", "monster.com", "dice.com", "simplyhired.com")
# Application platforms where the company is the first part of the path ...
ATS_PATH = ("greenhouse.io", "jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com", "apply.workable.com",
            "jobs.smartrecruiters.com", "jobs.jobvite.com")
# ... or the first part of the address (acme.wd5.myworkdayjobs.com, careers-acme.icims.com).
ATS_SUBDOMAIN = ("myworkdayjobs.com", "bamboohr.com", "recruitee.com", "breezy.hr", "applytojob.com", "icims.com",
                 "teamtailor.com", "pinpointhq.com", "rippling-ats.com")
GENERIC_LABELS = {"www", "careers", "career", "jobs", "job", "apply", "boards", "job-boards", "hire", "talent",
                  "recruiting", "work", "join"}


def _company_name(slug: str) -> str:
    """'acme-health' -> 'Acme Health'; 'OnePay' stays as written."""
    words = [w for w in re.split(r"[-_.\s]+", slug) if w]
    return " ".join(w if any(c.isupper() for c in w) else w.capitalize() for w in words)


def company_from_url(url: str) -> str | None:
    """A best guess at the employer from a posting link, for when the page doesn't say:
    jobs.lever.co/acme and careers.acme.com both give "Acme". None for job listing sites."""
    url = normalize_input_url(url)
    host = _host(url)
    if not host or any(host == d or host.endswith("." + d) for d in LISTING_SITES):
        return None
    parts = urlsplit(url)
    path = [p for p in parts.path.split("/") if p]
    for domain in ATS_PATH:
        if host == domain or host.endswith("." + domain):
            slug = parse_qs(parts.query).get("for", [""])[0] or next((p for p in path if p.lower() not in ("embed", "job_app", "en-us", "en")), "")
            return _company_name(slug) if slug else None
    labels = host.split(".")
    for domain in ATS_SUBDOMAIN:
        if host.endswith("." + domain):
            first = re.sub(r"^careers?-", "", labels[0])
            return _company_name(first) if first not in GENERIC_LABELS else None
    # The company's own site: the name just before the top-level domain (acme.co.uk -> acme).
    core = [label for label in labels if label not in GENERIC_LABELS]
    if len(core) >= 3 and core[-2] in ("co", "com", "org", "net", "ac") and len(core[-1]) == 2:
        core = core[:-1]
    return _company_name(core[-2]) if len(core) >= 2 else None


def fetch(url: str, client: httpx.Client | None = None) -> FetchResult:
    url = normalize_input_url(url)
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return FetchResult(False, url, reason="That doesn't look like a web address.")

    domain = blocked_domain(url)
    if domain:
        return FetchResult(
            False, url,
            reason=f"{domain} doesn't allow automated reading, so the app doesn't try. "
            "Paste the posting text below, or use the company's own careers page link.",
        )

    own_client = client is None
    client = client or httpx.Client(
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
    )
    try:
        return _fetch(url, client)
    finally:
        if own_client:
            client.close()


def _fetch(url: str, client: httpx.Client) -> FetchResult:
    try:
        # Redirects are followed one at a time so a link that leads to a site on the
        # no-fetch list (an aggregator forwarding to Indeed, say) stops before it's requested.
        for _ in range(MAX_REDIRECTS + 1):
            response = client.get(url, follow_redirects=False)
            if not response.is_redirect:
                break
            url = urljoin(str(response.url), response.headers["location"])
            if domain := blocked_domain(url):
                return FetchResult(
                    False, url,
                    reason=f"That link leads to {domain}, which doesn't allow automated reading, so the app "
                    "stopped there. Paste the posting text below, or use the company's own careers page link.",
                )
        else:
            return FetchResult(False, url, reason="That link redirects too many times.")
    except httpx.TimeoutException:
        return FetchResult(False, url, reason="The site took too long to respond.")
    except httpx.HTTPError:
        return FetchResult(False, url, reason="Couldn't connect to that site.")

    final_url = str(response.url)
    status = response.status_code
    if status in (404, 410):
        return FetchResult(False, final_url, reason="The posting wasn't found. It may have expired or been taken down.")
    if status in (401, 403, 429):
        return FetchResult(False, final_url, reason="The site blocked the request or needs a login.")
    if status >= 400:
        return FetchResult(False, final_url, reason=f"The site returned an error (HTTP {status}).")
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        return FetchResult(False, final_url, reason="That link isn't a web page (it may be a PDF or a download).")

    result = extract(response.text, final_url)
    if not result.ok and (posting := greenhouse_posting(final_url, client)):
        return posting
    return result


def extract(html: str, url: str = "") -> FetchResult:
    """Pull the posting text out of a page. Prefers the structured JobPosting data many
    job boards embed (it survives JavaScript-heavy pages), else the main page text."""
    hints, structured = _job_posting_data(html)
    text = structured if len(structured) >= MIN_CHARS else ""
    if not text:
        text = trafilatura.extract(
            html, url=url or None, output_format="markdown", include_tables=True,
            include_comments=False, include_links=False, favor_recall=True,
        ) or ""
    text = text.strip()

    if len(text) < MIN_CHARS:
        lowered = (text + " " + _visible_text(html)[:3000]).lower()
        if any(h in lowered for h in JS_HINTS):
            reason = "This page builds itself with JavaScript, so there was nothing to read."
        elif any(h in lowered for h in LOGIN_HINTS):
            reason = "This page needs a login to show the posting."
        else:
            reason = "The page had too little text to be a job posting."
        return FetchResult(False, url, text=text, reason=reason, hints=hints)

    trimmed = len(text) > MAX_CHARS
    if trimmed:
        text = text[:MAX_CHARS].rsplit("\n", 1)[0]
    return FetchResult(True, url, text=text, trimmed=trimmed, hints=hints)


def trim(text: str) -> tuple[str, bool]:
    """Apply the same length cap to pasted text."""
    text = text.strip()
    if len(text) <= MAX_CHARS:
        return text, False
    return text[:MAX_CHARS].rsplit("\n", 1)[0], True


# --- schema.org JobPosting ---------------------------------------------------

LD_JSON_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)


def _job_posting_data(html: str) -> tuple[dict, str]:
    for block in LD_JSON_RE.findall(html):
        try:
            data = json.loads(unescape(block.strip()))
        except ValueError:
            continue
        for item in _walk(data):
            types = item.get("@type")
            types = types if isinstance(types, list) else [types]
            if "JobPosting" not in types:
                continue
            title = _clean(item.get("title"))
            org = item.get("hiringOrganization") or {}
            company = _clean(org.get("name") if isinstance(org, dict) else org)
            location = _location(item.get("jobLocation"))
            body = _posting(title, company, location, html_to_text(item.get("description") or ""))
            return {"title": title, "company": company}, body
    return {}, ""


def _posting(title: str | None, company: str | None, location: str | None, description: str) -> str:
    header = [f"Job title: {title}" if title else "",
              f"Company: {company}" if company else "",
              f"Location: {location}" if location else ""]
    return ("\n".join(h for h in header if h) + "\n\n" + description).strip()


# --- Greenhouse careers pages --------------------------------------------------

GREENHOUSE_JOB_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"


def greenhouse_job(url: str) -> tuple[list[str], str] | None:
    """The Greenhouse board names to try and the job ID a link points to, or None.

    On greenhouse.io the board is in the link. On a company's own careers page the job ID
    is a gh_jid parameter or a long number at the end of the path, and the board is
    guessed from the company's domain (cribl.io -> "cribl"), so the answer is checked
    against the page's site in greenhouse_posting."""
    url = normalize_input_url(url)
    parts = urlsplit(url)
    host = _host(url)
    query = parse_qs(parts.query)
    path = [p for p in parts.path.split("/") if p]
    if host == "greenhouse.io" or host.endswith(".greenhouse.io"):
        board = query.get("for", [""])[0] or (path[0] if path and path[0] != "embed" else "")
        job_id = (query.get("token", [""])[0] or query.get("gh_jid", [""])[0]
                  or next((p for p in reversed(path) if p.isdigit()), ""))
        boards = [board.lower()] if board else []
    else:
        job_id = query.get("gh_jid", [""])[0] or next((p for p in reversed(path) if p.isdigit() and len(p) >= 7), "")
        name = (company_from_url(url) or "").lower()
        boards = list(dict.fromkeys(b for b in (name.replace(" ", ""), name.replace(" ", "-")) if b))
    if not job_id.isdigit() or not boards:
        return None
    return boards, job_id


def _site(host: str) -> str:
    """careers.acme.com and www.acme.com -> acme.com; jobs.acme.co.uk -> acme.co.uk."""
    labels = [label for label in host.lower().split(".") if label]
    keep = 3 if len(labels) >= 3 and labels[-2] in ("co", "com", "org", "net", "ac") and len(labels[-1]) == 2 else 2
    return ".".join(labels[-keep:])


def greenhouse_posting(url: str, client: httpx.Client) -> FetchResult | None:
    """The posting from Greenhouse's public job API, for a careers page that couldn't be
    read. None when the link has no Greenhouse job ID, the job isn't there, or it belongs
    to a different site than the page."""
    found = greenhouse_job(url)
    if not found:
        return None
    boards, job_id = found
    on_greenhouse = _host(url).endswith("greenhouse.io")
    for board in boards:
        try:
            response = client.get(GREENHOUSE_JOB_API.format(board=board, job_id=job_id), follow_redirects=False)
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            continue
        try:
            data = response.json()
        except ValueError:
            return None
        if not isinstance(data, dict):
            continue
        if not on_greenhouse and _site(_host(str(data.get("absolute_url") or ""))) != _site(_host(url)):
            continue
        title, company = _clean(data.get("title")), _clean(data.get("company_name"))
        location = _clean((data.get("location") or {}).get("name"))
        text = _posting(title, company, location, html_to_text(data.get("content") or ""))
        if len(text) < MIN_CHARS:
            return None
        text, trimmed = trim(text)
        return FetchResult(True, url, text=text, trimmed=trimmed, hints={"title": title, "company": company})
    return None


def _walk(data):
    if isinstance(data, list):
        for item in data:
            yield from _walk(item)
    elif isinstance(data, dict):
        yield data
        if "@graph" in data:
            yield from _walk(data["@graph"])


def _clean(value) -> str | None:
    return " ".join(str(value).split()) if value else None


def _location(value) -> str | None:
    places = value if isinstance(value, list) else [value]
    names = []
    for place in places:
        if not isinstance(place, dict):
            continue
        address = place.get("address") or {}
        if isinstance(address, dict):
            parts = [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")]
            parts = [p.get("name") if isinstance(p, dict) else p for p in parts]
            name = ", ".join(str(p) for p in parts if p)
            if name:
                names.append(name)
    return "; ".join(names) or None


class _TextParser(HTMLParser):
    BLOCKS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(unescape(html) if "&lt;" in html else html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _visible_text(html: str) -> str:
    return html_to_text(html)
