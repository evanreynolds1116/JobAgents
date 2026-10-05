"""Adzuna job search API (https://developer.adzuna.com/docs/search).

Parameter names follow Adzuna's published spec (developer.adzuna.com/swagger/spec/test2.json).
Free tier: 250 calls a day, 2,500 a month, up to 50 results a call. Keys come from .env
and are never logged.
"""

from dataclasses import dataclass

import httpx

from search.criteria import SearchCriteria
from search.normalize import Job, guess_setting, parse_time

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
COUNTRY = "us"
RESULTS_PER_PAGE = 50
TIMEOUT = 30.0


class AdzunaError(Exception):
    """A call failed; the message is for you."""


@dataclass(frozen=True)
class Query:
    kind: str                  # "city" (hybrid and on-site near a city) or "remote" (nationwide)
    title: str
    city: str | None = None
    radius_km: int | None = None
    radius_miles: int | None = None

    @property
    def label(self) -> str:
        return f"{self.title} near {self.city}" if self.kind == "city" else f"{self.title}, remote (US)"


def build_queries(criteria: SearchCriteria) -> list[Query]:
    """One query per title per city, plus one nationwide remote query per title."""
    queries = []
    titles = [t.strip() for t in criteria.titles if t.strip()]
    local = set(criteria.settings) & {"hybrid", "onsite"}
    for title in titles:
        if local:
            for city in criteria.cities:
                queries.append(Query("city", title, city.name, city.radius_km, city.radius_miles))
        if "remote" in criteria.settings:
            queries.append(Query("remote", title))
    return queries


def params(query: Query, criteria: SearchCriteria, app_id: str, app_key: str) -> dict:
    p = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": RESULTS_PER_PAGE,
        "title_only": query.title,
        "max_days_old": criteria.max_days_old,
        "sort_by": "date",
        "content-type": "application/json",
    }
    if query.kind == "city":
        p["where"] = query.city
        p["distance"] = query.radius_km
    else:
        p["what"] = "remote"
    if criteria.salary_min:
        p["salary_min"] = criteria.salary_min
    if criteria.salary_max:
        p["salary_max"] = criteria.salary_max
    if criteria.salary_min or criteria.salary_max:
        p["salary_include_unknown"] = "1"  # keep postings with no salary; they're labeled instead
    return p


def search(query: Query, criteria: SearchCriteria, app_id: str, app_key: str,
           client: httpx.Client | None = None) -> list[dict]:
    """One API call (page 1, up to 50 results). Returns Adzuna's raw result objects."""
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        response = client.get(BASE_URL.format(country=COUNTRY, page=1),
                              params=params(query, criteria, app_id, app_key),
                              headers={"Accept": "application/json"})
    except httpx.TimeoutException as exc:
        raise AdzunaError("Adzuna took too long to respond.") from exc
    except httpx.HTTPError as exc:
        raise AdzunaError("Couldn't reach Adzuna. Check your internet connection.") from exc
    finally:
        if own:
            client.close()
    if response.status_code in (401, 403):
        raise AdzunaError("Adzuna rejected the app ID or key in .env.")
    if response.status_code == 429:
        raise AdzunaError("Adzuna says the rate limit was reached. Try again later.")
    if response.status_code >= 400:
        raise AdzunaError(f"Adzuna returned an error (HTTP {response.status_code}).")
    try:
        return response.json().get("results", [])
    except ValueError as exc:
        raise AdzunaError("Adzuna sent a response the app couldn't read.") from exc


def to_job(ad: dict) -> Job:
    company = (ad.get("company") or {}).get("display_name") or "Unknown company"
    location = (ad.get("location") or {}).get("display_name") or ""
    title = (ad.get("title") or "").strip()
    description = (ad.get("description") or "").strip()

    def number(key):
        value = ad.get(key)
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    return Job(
        source="adzuna",
        source_id=str(ad.get("id", "")),
        title=title,
        company=company.strip(),
        location=location,
        work_setting=guess_setting(title, description, location),
        salary_min=number("salary_min"),
        salary_max=number("salary_max"),
        salary_estimated=str(ad.get("salary_is_predicted", "0")) == "1",
        posted_at=parse_time(ad.get("created")),
        apply_url=ad.get("redirect_url") or "",
        description=description,
        extra={"latitude": ad.get("latitude"), "longitude": ad.get("longitude"),
               "contract_time": ad.get("contract_time"), "contract_type": ad.get("contract_type")},
    )
