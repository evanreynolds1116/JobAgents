"""Job fetcher: URL -> clean posting text, or a reason to ask you to paste it.

One request per URL you paste, made the way a browser visit would be. It never
logs in, retries around blocks or tries to get past bot protection; anything it
can't read falls back to pasting the text (spec: Edge cases & error handling).
"""

import json
import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx
import trafilatura

MAX_CHARS = 30_000   # cap on posting text sent to Claude; you're warned if it's trimmed
MIN_CHARS = 400      # less than this is a login wall, an error page or a JavaScript shell
TIMEOUT = 20.0
# Says what it is rather than imitating a browser; sites that refuse it get the paste fallback.
USER_AGENT = "Mozilla/5.0 (compatible; JobAssistant/0.1; personal job-application helper)"

# Sites whose terms don't allow automated reading, or that need a login to show
# a posting. The app skips the request and asks for the pasted text instead.
NO_FETCH_DOMAINS = ("linkedin.com", "indeed.com", "glassdoor.com", "jobright.ai", "hiring.cafe")

LOGIN_HINTS = ("sign in", "log in", "login", "create an account", "join now")
JS_HINTS = ("enable javascript", "javascript is required", "javascript is disabled")


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
        follow_redirects=True, timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
    )
    try:
        response = client.get(url)
    except httpx.TimeoutException:
        return FetchResult(False, url, reason="The site took too long to respond.")
    except httpx.HTTPError:
        return FetchResult(False, url, reason="Couldn't connect to that site.")
    finally:
        if own_client:
            client.close()

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

    return extract(response.text, final_url)


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
            description = _html_to_text(item.get("description") or "")
            header = [f"Job title: {title}" if title else "",
                      f"Company: {company}" if company else "",
                      f"Location: {location}" if location else ""]
            body = "\n".join(h for h in header if h) + "\n\n" + description
            return {"title": title, "company": company}, body.strip()
    return {}, ""


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


def _html_to_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(unescape(html) if "&lt;" in html else html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _visible_text(html: str) -> str:
    return _html_to_text(html)
