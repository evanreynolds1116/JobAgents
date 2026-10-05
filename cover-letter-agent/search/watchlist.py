"""Company watch list: open jobs read from companies' public job boards (spec: Data
sources; Milestone 12).

Greenhouse, Lever and Ashby each publish a free, keyless API for a company's board, with
full job descriptions. One call per company per run. Jobs are matched to a saved search
by title, then go through the same salary, exclusion, work-setting and location rules as
Adzuna results. The date rule is skipped: boards keep jobs open for months, and a job
already seen isn't shown as new again, so only newly posted ones appear after the first run.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

import httpx

from agent.fetch import USER_AGENT, html_to_text
from search import places
from search.adzuna import Query
from search.criteria import SearchCriteria
from search.normalize import Job, guess_setting, parse_time

PLATFORMS = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby"}
API = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{board}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true",
}
TIMEOUT = 30.0
US_NAMES = {"us", "usa", "united states", "united states of america"}


class WatchError(Exception):
    """A board couldn't be read; the message is for you."""


@dataclass(frozen=True)
class Board:
    platform: str
    board: str


def parse_board(link: str) -> Board | None:
    """The board behind a careers link, for example job-boards.greenhouse.io/axios,
    jobs.lever.co/acme or jobs.ashbyhq.com/acme. None if it isn't one of the three."""
    link = link.strip()
    if "://" not in link:
        link = "https://" + link
    parts = urlsplit(link)
    host = (parts.hostname or "").lower()
    path = [p for p in parts.path.split("/") if p]
    if host.endswith("greenhouse.io"):
        board = parse_qs(parts.query).get("for", [""])[0] or (path[0] if path and path[0] != "embed" else "")
        return Board("greenhouse", board.lower()) if board else None
    if host in ("jobs.lever.co", "jobs.eu.lever.co") and path:
        return Board("lever", path[0].lower())
    if host == "jobs.ashbyhq.com" and path:
        return Board("ashby", path[0])
    return None


def fetch_board(platform: str, board: str, client: httpx.Client | None = None) -> list[dict]:
    """Raw job objects from one board (one call)."""
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    try:
        response = client.get(API[platform].format(board=board))
    except httpx.TimeoutException as exc:
        raise WatchError("the job board took too long to respond.") from exc
    except httpx.HTTPError as exc:
        raise WatchError("couldn't reach the job board.") from exc
    finally:
        if own:
            client.close()
    if response.status_code == 404:
        raise WatchError("no job board found. Check the careers link.")
    if response.status_code >= 400:
        raise WatchError(f"the job board returned an error (HTTP {response.status_code}).")
    try:
        data = response.json()
    except ValueError as exc:
        raise WatchError("the job board sent something the app couldn't read.") from exc
    jobs = data if platform == "lever" else data.get("jobs")
    if not isinstance(jobs, list):
        raise WatchError("the job board sent something the app couldn't read.")
    return jobs


# Normalizing ---------------------------------------------------------------------


def _salary(low, high, yearly: bool, currency: str | None) -> tuple[float | None, float | None]:
    if not yearly or (currency or "USD").upper() != "USD":
        return None, None
    return (float(low) if low else None), (float(high) if high else None)


def to_job(platform: str, raw: dict, company: str) -> Job:
    """One raw job -> the app's job record. `extra` carries every location given (for the
    distance check) and the country when the board says."""
    salary_min = salary_max = None
    if platform == "greenhouse":
        title, url = raw.get("title") or "", raw.get("absolute_url") or ""
        locations = [(raw.get("location") or {}).get("name") or ""]
        description = html_to_text(raw.get("content") or "")
        posted = parse_time(raw.get("first_published") or raw.get("updated_at"))
        setting, country = None, None
        company = raw.get("company_name") or company
    elif platform == "lever":
        cats = raw.get("categories") or {}
        title, url = raw.get("text") or "", raw.get("hostedUrl") or ""
        locations = cats.get("allLocations") or [cats.get("location") or ""]
        lists = "\n\n".join(f"{item.get('text', '')}\n{html_to_text(item.get('content') or '')}"
                            for item in raw.get("lists") or [])
        description = "\n\n".join(p for p in (raw.get("descriptionPlain"), lists, raw.get("additionalPlain")) if p)
        created = raw.get("createdAt")
        posted = datetime.fromtimestamp(created / 1000).isoformat(timespec="seconds") if created else None
        setting = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}.get(raw.get("workplaceType") or "")
        country = raw.get("country")
        pay = raw.get("salaryRange") or {}
        salary_min, salary_max = _salary(pay.get("min"), pay.get("max"),
                                         "year" in (pay.get("interval") or ""), pay.get("currency"))
    else:  # ashby
        title, url = raw.get("title") or "", raw.get("jobUrl") or ""
        locations = [raw.get("location") or ""] + [s.get("location") or "" for s in raw.get("secondaryLocations") or []]
        description = raw.get("descriptionPlain") or html_to_text(raw.get("descriptionHtml") or "")
        posted = parse_time(raw.get("publishedAt"))
        setting = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}.get(
            (raw.get("workplaceType") or "").lower()) or ("remote" if raw.get("isRemote") else None)
        country = ((raw.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
        for part in ((raw.get("compensation") or {}).get("summaryComponents") or []):
            if part.get("compensationType") == "Salary":
                salary_min, salary_max = _salary(part.get("minValue"), part.get("maxValue"),
                                                 "YEAR" in (part.get("interval") or ""), part.get("currencyCode"))
    location = "; ".join(loc for loc in locations if loc)
    return Job(
        source=platform, source_id=str(raw.get("id", "")), title=title.strip(), company=company.strip(),
        location=location, work_setting=setting or guess_setting(title, location, description[:3000]),
        salary_min=salary_min, salary_max=salary_max, salary_estimated=False, posted_at=posted,
        apply_url=url, description=description.strip(),
        extra={"locations": [loc for loc in locations if loc], "country": country, "board_setting": setting},
    )


def fetch_jobs(company: dict, client: httpx.Client | None = None) -> list[Job]:
    """Every open job at a watched company, as job records."""
    raws = fetch_board(company["platform"], company["board"], client)
    return [to_job(company["platform"], raw, company["name"]) for raw in raws]


# Matching a saved search ----------------------------------------------------------


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+", text.lower()))


def matching_title(job_title: str, titles: list[str]) -> str | None:
    """The first search title whose words all appear in the job's title: "Backend Engineer"
    matches "Senior Backend Software Engineer"."""
    have = _words(job_title)
    return next((t for t in titles if t.strip() and _words(t) <= have), None)


def coordinates(location: str) -> tuple[float, float] | None:
    """Coordinates for a location as boards write it: "Nashville, TN",
    "San Francisco, California, United States", "Remote; Charlotte, NC preferred"."""
    for part in re.split(r";|\||/|\bor\b", location):
        part = re.sub(r"\b(preferred|hybrid|remote|on-?site|office)\b", "", part, flags=re.I).strip(" ,-()")
        pieces = [p.strip() for p in part.split(",") if p.strip()]
        for guess in (", ".join(pieces[:2]), part):
            if guess and (spot := places.lookup(guess)):
                return spot
    return None


def in_us(country: str | None) -> bool:
    return country is None or country.strip().lower() in US_NAMES


def contexts_for(job: Job, title: str, criteria: SearchCriteria) -> list[Query]:
    """The ways a watch-list job can qualify for a search, as Adzuna-style queries: remote
    (anywhere in the US) if remote is picked, and each city it's within the radius of."""
    queries = []
    if "remote" in criteria.settings and in_us(job.extra.get("country")):
        queries.append(Query("remote", title))
    if set(criteria.settings) & {"hybrid", "onsite"}:
        spots = [s for loc in job.extra.get("locations", []) if (s := coordinates(loc))]
        for city in criteria.cities:
            center = places.lookup(city.name)
            if center and any(places.miles_between(center, s) <= city.radius_miles for s in spots):
                queries.append(Query("city", title, city.name, city.radius_km, city.radius_miles))
    return queries
