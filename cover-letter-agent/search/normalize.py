"""Turn source results into one job record shape, label the work setting, and build
the duplicate key (spec: How a search run works, steps 3 and 4)."""

import re
from dataclasses import dataclass, field
from datetime import datetime

COMPANY_SUFFIXES = r"(,?\s+(inc|incorporated|corp|corporation|co|company|llc|ltd|limited|plc|group|holdings))+\.?$"


@dataclass
class Job:
    source: str
    source_id: str
    title: str
    company: str
    location: str
    work_setting: str            # remote, hybrid, onsite or unknown
    salary_min: float | None
    salary_max: float | None
    salary_estimated: bool
    posted_at: str | None        # local ISO time
    apply_url: str
    description: str
    extra: dict = field(default_factory=dict)

    @property
    def dedupe_key(self) -> str:
        return dedupe_key(self.company, self.title, "remote" if self.work_setting == "remote" else self.location)


def _clean(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def dedupe_key(company: str, title: str, location: str) -> str:
    """Same company, title and place -> same key, however each source spells them."""
    company = re.sub(COMPANY_SUFFIXES, "", (company or "").strip(), flags=re.I)
    city = (location or "").split(",")[0]
    return " | ".join(_clean(part) for part in (company, title or "", city))


# Work setting -----------------------------------------------------------------------
# Milestone 10 labels the setting from the text; Milestone 11 has Claude classify it.

NOT_REMOTE = re.compile(r"\b(not|no|non)[\s-]+remote\b|\bremote\s+(is\s+)?not\b", re.I)
HYBRID = re.compile(r"\bhybrid\b", re.I)
REMOTE = re.compile(r"\b(remote|work from home|wfh|telecommut\w*|distributed team)\b", re.I)
ONSITE = re.compile(r"\b(on[\s-]?site|in[\s-]office|in[\s-]person)\b", re.I)


def guess_setting(*texts: str) -> str:
    text = " ".join(t for t in texts if t)
    if HYBRID.search(text):
        return "hybrid"
    if NOT_REMOTE.search(text):
        return "onsite"
    if REMOTE.search(text):
        return "remote"
    if ONSITE.search(text):
        return "onsite"
    return "unknown"


# Dates and salary ------------------------------------------------------------------


def parse_time(stamp: str | None) -> str | None:
    """Source timestamps (often UTC with 'Z') -> local ISO time, seconds precision."""
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo:
        moment = moment.astimezone().replace(tzinfo=None)
    return moment.isoformat(timespec="seconds")


def salary_label(job: dict) -> str:
    low, high = job.get("salary_min"), job.get("salary_max")
    if not low and not high:
        return "Not listed"

    def k(n):
        return f"${round(n / 1000)}k"

    text = k(low) if low and (not high or round(low) == round(high)) else (
        f"{k(low)}–{k(high)}" if low else f"up to {k(high)}")
    return text + (" est." if job.get("salary_estimated") else "")


def salary_outside(job: Job, low: int | None, high: int | None) -> bool:
    """True only when the posting's stated range misses yours. No salary, or only Adzuna's
    estimate, is never outside; those jobs are kept and labeled."""
    if job.salary_estimated or (job.salary_min is None and job.salary_max is None):
        return False
    top = job.salary_max if job.salary_max is not None else job.salary_min
    bottom = job.salary_min if job.salary_min is not None else job.salary_max
    if low and top < low:
        return True
    if high and bottom > high:
        return True
    return False
