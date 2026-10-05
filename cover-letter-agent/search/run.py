"""Run saved searches (spec: How a search run works, steps 1 to 5).

Builds the queries, checks the Adzuna allowance first, calls Adzuna, normalizes each
result, applies the date, salary, exclusion and location rules, and stores new jobs.
Fit scoring (step 6) comes in Milestone 11.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import config
from search import adzuna
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
    finished_at: str = ""

    def summary(self) -> str:
        parts = [f"{self.new} new job{'s' if self.new != 1 else ''}",
                 f"{self.fetched} found", f"{self.duplicates} already seen"]
        parts += [f"{n} {reason}" for reason, n in self.dropped.most_common()]
        return f"{self.calls} Adzuna call{'s' if self.calls != 1 else ''}: " + ", ".join(parts) + "."


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
    if job.posted_at and datetime.fromisoformat(job.posted_at) < now - timedelta(days=criteria.max_days_old):
        return "older than your date range"
    text = f"{job.title} {job.description}".lower()
    company = job.company.lower()
    if any(c.strip() and c.strip().lower() in company for c in criteria.exclude_companies):
        return "from excluded companies"
    if any(k.strip() and k.strip().lower() in text for k in criteria.exclude_keywords):
        return "with excluded keywords"
    if salary_outside(job, criteria.salary_min, criteria.salary_max):
        return "outside your salary range"
    if query.kind == "remote":
        # The nationwide query can return jobs anywhere; only remote ones are kept.
        if job.work_setting != "remote":
            return "not remote and outside your cities"
    elif job.work_setting != "unknown" and job.work_setting not in criteria.settings:
        return "in a work setting you didn't pick"
    return None


def run_searches(searches: list[dict], client=None, now: datetime | None = None) -> RunResult:
    settings = config.load_settings()
    if settings.adzuna_status != "ok":
        raise adzuna.AdzunaError("Add ADZUNA_APP_ID and ADZUNA_APP_KEY to .env first.")
    check_allowance(planned_calls(searches))
    now = now or datetime.now()
    stamp = now.isoformat(timespec="seconds")
    result = RunResult()
    seen_this_run: set[str] = set()
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
                job = adzuna.to_job(ad)
                result.fetched += 1
                if reason := keep(job, query, criteria, now):
                    result.dropped[reason] += 1
                    continue
                if job.dedupe_key in seen_this_run:
                    result.duplicates += 1
                    continue
                seen_this_run.add(job.dedupe_key)
                if store.upsert(job, saved["id"], stamp):
                    result.new += 1
                else:
                    result.duplicates += 1
        store.mark_run(saved["id"], stamp)
    result.finished_at = stamp
    return result
