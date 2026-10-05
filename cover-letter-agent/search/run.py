"""Run saved searches (spec: How a search run works, steps 1 to 6).

Builds the queries, checks the Adzuna allowance first, calls Adzuna and reads each
watch-list company's job board, normalizes each result and applies the date, salary and
exclusion rules. Postings the app hasn't seen
before are then labeled and scored by Claude (search/score.py), the work-setting and
location rules run on Claude's labels, and the new jobs are stored with their fit.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import config
from search import adzuna, places, score, watchlist
from search.criteria import SearchCriteria
from search.normalize import Job, salary_outside
from storage import jobs as store

DAILY_LIMIT = 250
MONTHLY_LIMIT = 2500


class UsageLimit(Exception):
    """Running now would go past Adzuna's free allowance."""


@dataclass
class RunResult:
    calls: int = 0
    fetched: int = 0
    new: int = 0
    duplicates: int = 0
    dropped: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)
    scored: int = 0
    companies: int = 0  # watch-list boards read
    finished_at: str = ""

    def summary(self) -> str:
        parts = [f"{self.new} new job{'s' if self.new != 1 else ''}",
                 f"{self.fetched} found", f"{self.duplicates} already seen"]
        parts += [f"{n} {reason}" for reason, n in self.dropped.most_common()]
        sources = f"{self.calls} Adzuna call{'s' if self.calls != 1 else ''}"
        if self.companies:
            sources += f" and {self.companies} watch-list compan{'ies' if self.companies != 1 else 'y'}"
        text = sources + ": " + ", ".join(parts) + "."
        if self.scored:
            text += f" Claude checked {self.scored} posting{'s' if self.scored != 1 else ''}."
        return text


def planned_calls(searches: list[dict]) -> int:
    return sum(len(adzuna.build_queries(s["criteria"])) for s in searches)


def check_allowance(calls: int) -> None:
    today, month = store.calls_today("adzuna"), store.calls_this_month("adzuna")
    if today + calls > DAILY_LIMIT:
        raise UsageLimit(f"This run needs {calls} Adzuna calls and {today} of today's {DAILY_LIMIT} are used. "
                         "Try again tomorrow, or remove some titles or cities.")
    if month + calls > MONTHLY_LIMIT:
        raise UsageLimit(f"This run needs {calls} Adzuna calls and {month} of this month's {MONTHLY_LIMIT} "
                         "are used.")


def keep(job: Job, query: adzuna.Query, criteria: SearchCriteria, now: datetime) -> str | None:
    """None to keep the job, otherwise the reason it was dropped."""
    return prefilter(job, criteria, now) or setting_rule(job, query, criteria)


def prefilter(job: Job, criteria: SearchCriteria, now: datetime, dated: bool = True) -> str | None:
    """The rules that don't need the work setting, checked before anything is sent to Claude.
    `dated=False` skips the date rule: watch-list jobs are open now, however long ago they
    were posted, and the ones already seen aren't shown as new again."""
    if dated and job.posted_at and datetime.fromisoformat(job.posted_at) < now - timedelta(days=criteria.max_days_old):
        return "older than your date range"
    text = f"{job.title} {job.description}".lower()
    company = job.company.lower()
    if any(c.strip() and c.strip().lower() in company for c in criteria.exclude_companies):
        return "from excluded companies"
    if any(k.strip() and k.strip().lower() in text for k in criteria.exclude_keywords):
        return "with excluded keywords"
    if salary_outside(job, criteria.salary_min, criteria.salary_max):
        return "outside your salary range"
    return None


def setting_rule(job: Job, query: adzuna.Query, criteria: SearchCriteria) -> str | None:
    """Work-setting and location rules, run on Claude's label when there is one."""
    if query.kind == "remote":
        # The nationwide query can return jobs anywhere; only remote ones are kept.
        if job.work_setting != "remote":
            return "not remote and outside your cities"
    elif job.work_setting != "unknown" and job.work_setting not in criteria.settings:
        return "in a work setting you didn't pick"
    elif job.work_setting != "remote" and outside_radius(job, query):
        return "outside your cities' radius"
    return None


def outside_radius(job: Job, query: adzuna.Query) -> bool:
    """Adzuna's distance filter is approximate, so check the job's coordinates against the
    city's. Jobs without coordinates, or cities not in the list, are left to Adzuna's filter."""
    center = places.lookup(query.city or "")
    try:
        spot = (float(job.extra["latitude"]), float(job.extra["longitude"]))
    except (KeyError, TypeError, ValueError):
        return False
    return bool(center and query.radius_miles) and places.miles_between(center, spot) > query.radius_miles


@dataclass
class Candidate:
    """A posting seen in this run, with each search and query that found it and passed its
    date, salary and exclusion rules."""
    job: Job
    contexts: list[tuple[adzuna.Query, SearchCriteria, int]] = field(default_factory=list)
    first_drop: str | None = None


def run_searches(searches: list[dict], client=None, now: datetime | None = None, scorer=None) -> RunResult:
    settings = config.load_settings()
    if settings.adzuna_status != "ok":
        raise adzuna.AdzunaError("Add ADZUNA_APP_ID and ADZUNA_APP_KEY to .env first.")
    check_allowance(planned_calls(searches))
    scorer = scorer or score.score_jobs
    now = now or datetime.now()
    stamp = now.isoformat(timespec="seconds")
    result = RunResult()

    # 1-5: collect each posting once, with every search and query that found it.
    candidates: list[Candidate] = []
    index: dict[str, Candidate] = {}

    def collect(job: Job, queries: list[adzuna.Query], criteria: SearchCriteria, search_id: int,
                dated: bool = True) -> None:
        result.fetched += 1
        keys = [f"{job.source}:{job.source_id}" if job.source_id else "", job.dedupe_key]
        cand = next((index[k] for k in keys if k and k in index), None)
        if cand:
            result.duplicates += 1  # the same posting from another query or source
        else:
            cand = Candidate(job)
            candidates.append(cand)
            index.update({k: cand for k in keys if k})
        # Rules are checked on this copy; a duplicate can come from another board or place.
        if reason := prefilter(job, criteria, now, dated) or (None if queries else "outside your cities"):
            cand.first_drop = cand.first_drop or reason
        else:
            if not cand.contexts:
                cand.job = job  # the first copy that qualifies is the one stored
            cand.contexts += [(query, criteria, search_id) for query in queries]

    for saved in searches:
        criteria = saved["criteria"]
        for query in adzuna.build_queries(criteria):
            store.record_calls("adzuna")
            result.calls += 1
            try:
                ads = adzuna.search(query, criteria, settings.adzuna_app_id, settings.adzuna_app_key, client)
            except adzuna.AdzunaError as exc:
                result.errors.append(f"{query.label}: {exc}")
                continue
            for ad in ads:
                collect(adzuna.to_job(ad), [query], criteria, saved["id"])

    # Watch list: one call per company, then each job is matched to the searches by title.
    watched: list[Job] = []
    for company in store.list_companies():
        result.companies += 1
        try:
            watched += watchlist.fetch_jobs(company, client)
        except watchlist.WatchError as exc:
            result.errors.append(f"{company['name']} ({watchlist.PLATFORMS[company['platform']]}): {exc}")
    for saved in searches:
        criteria = saved["criteria"]
        for job in watched:
            if title := watchlist.matching_title(job.title, criteria.titles):
                collect(job, watchlist.contexts_for(job, title, criteria), criteria, saved["id"], dated=False)

    to_score = []
    for cand in candidates:
        if not cand.contexts:
            result.dropped[cand.first_drop] += 1
        elif job_id := store.known(cand.job):
            store.touch(job_id, stamp)  # already in the app: just note it was seen again
            result.duplicates += 1
        else:
            to_score.append(cand)

    # 6: Claude labels the work setting and scores fit, for new postings only.
    scores, errors = scorer([c.job for c in to_score])
    result.errors += errors
    result.scored = sum(1 for s in scores if s)
    for cand, s in zip(to_score, scores):
        job = cand.job
        if s:
            # A board that states the setting (Lever, Ashby) is trusted over a reading of the text.
            job.work_setting = job.extra.get("board_setting") or s.work_setting
            job.fit, job.fit_reason = s.fit, s.reason
        reasons = [setting_rule(job, query, criteria) for query, criteria, _ in cand.contexts]
        if None not in reasons:
            result.dropped[reasons[0]] += 1
            continue
        search_id = cand.contexts[reasons.index(None)][2]
        if store.upsert(job, search_id, stamp):
            result.new += 1
        else:
            result.duplicates += 1

    for saved in searches:
        store.mark_run(saved["id"], stamp)
    result.finished_at = stamp
    return result
