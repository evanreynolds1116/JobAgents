"""Saved searches, found jobs and API usage (spec: Phase 3, Storage)."""

import json
from datetime import date, datetime

from search.criteria import SearchCriteria
from search.normalize import Job
from storage.db import connect

STATUSES = ("new", "saved", "dismissed", "applying")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# Saved searches -----------------------------------------------------------------------


def save_search(name: str, criteria: SearchCriteria, search_id: int | None = None) -> int:
    payload = json.dumps(criteria.to_dict())
    with connect() as conn:
        if search_id:
            conn.execute("UPDATE saved_searches SET name = ?, criteria_json = ? WHERE id = ?",
                         (name.strip(), payload, search_id))
        else:
            search_id = conn.execute("INSERT INTO saved_searches (name, criteria_json) VALUES (?, ?)",
                                     (name.strip(), payload)).lastrowid
    conn.close()
    return search_id


def list_searches() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM saved_searches ORDER BY id").fetchall()
    conn.close()
    return [{**dict(r), "criteria": SearchCriteria.from_dict(json.loads(r["criteria_json"]))} for r in rows]


def delete_search(search_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))
    conn.close()


def mark_run(search_id: int, when: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE saved_searches SET last_run_at = ? WHERE id = ?", (when, search_id))
    conn.close()


# Jobs ------------------------------------------------------------------------------


def upsert(job: Job, search_id: int | None, seen_at: str) -> bool:
    """Store a job unless it's already known. Returns True if it's new.
    A job counts as known if the same source already gave it, or its duplicate key exists
    (same company, title and place from another source or an earlier run)."""
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM jobs WHERE (source = ? AND source_id = ? AND source_id != '') OR dedupe_key = ?",
            (job.source, job.source_id, job.dedupe_key),
        ).fetchone()
        if existing:
            conn.execute("UPDATE jobs SET last_seen_at = ? WHERE id = ?", (seen_at, existing["id"]))
            new = False
        else:
            conn.execute(
                """INSERT INTO jobs (dedupe_key, source, source_id, search_id, title, company, location,
                       work_setting, salary_min, salary_max, salary_estimated, posted_at, apply_url,
                       description, first_seen_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job.dedupe_key, job.source, job.source_id, search_id, job.title, job.company, job.location,
                 job.work_setting, job.salary_min, job.salary_max, int(job.salary_estimated), job.posted_at,
                 job.apply_url, job.description, seen_at, seen_at),
            )
            new = True
    conn.close()
    return new


def list_jobs(status: str = "new", hide_no_salary: bool = False) -> list[dict]:
    """Newest postings first (Milestone 11 sorts by fit, then date)."""
    query = "SELECT * FROM jobs WHERE status = ?"
    if hide_no_salary:
        query += " AND (salary_min IS NOT NULL OR salary_max IS NOT NULL)"
    query += " ORDER BY COALESCE(posted_at, first_seen_at) DESC, id DESC"
    with connect() as conn:
        rows = conn.execute(query, (status,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_jobs() -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
    conn.close()
    counts = {s: 0 for s in STATUSES}
    counts.update({r["status"]: r["n"] for r in rows})
    return counts


def set_status(job_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(status)
    with connect() as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.close()


# API usage --------------------------------------------------------------------------


def record_calls(service: str, calls: int = 1, day: date | None = None) -> None:
    day = (day or date.today()).isoformat()
    with connect() as conn:
        conn.execute(
            "INSERT INTO api_usage (day, service, calls) VALUES (?, ?, ?) "
            "ON CONFLICT (day, service) DO UPDATE SET calls = calls + excluded.calls",
            (day, service, calls),
        )
    conn.close()


def calls_today(service: str, day: date | None = None) -> int:
    day = (day or date.today()).isoformat()
    with connect() as conn:
        row = conn.execute("SELECT calls FROM api_usage WHERE day = ? AND service = ?", (day, service)).fetchone()
    conn.close()
    return row["calls"] if row else 0


def calls_this_month(service: str, day: date | None = None) -> int:
    month = (day or date.today()).isoformat()[:7]
    with connect() as conn:
        row = conn.execute("SELECT COALESCE(SUM(calls), 0) AS n FROM api_usage WHERE day LIKE ? AND service = ?",
                           (f"{month}-%", service)).fetchone()
    conn.close()
    return row["n"]
