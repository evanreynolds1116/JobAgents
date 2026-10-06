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
    fit: int | None = None       # 1 to 5 from Claude (Milestone 11); None if not scored
    fit_reason: str = ""

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


# Salary stated in a posting's text ----------------------------------------------------
# For the application detail page: most applications start from a pasted link, so the
# only place their pay appears is the saved posting. Read by code, not Claude.

_NUMBER = r"(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
_NOT_LARGE = r"(?!\s?(?:[mMbB]\b|mm\b|million|billion))"  # "$100M raised" isn't pay
_AMOUNT = r"\$\s?" + _NUMBER + r"\s?([kK]\b)?" + _NOT_LARGE
RANGE_RE = re.compile(_AMOUNT + r"\s*(?:-|–|—|to|and)\s*(?:USD\s*)?(?:\$\s?)?" + _NUMBER + r"\s?([kK]\b)?" + _NOT_LARGE)
SINGLE_RE = re.compile(_AMOUNT)
HOURLY_RE = re.compile(r"^\W{0,3}(?:USD\s*)?(?:per|an|/|a)\s*(?:hour|hr)\b|^\W{0,3}(?:USD\s*)?hourly\b", re.I)
PAY_WORDS = re.compile(r"\b(salary|compensation|pay|base|wage|OTE)\b", re.I)


@dataclass(frozen=True)
class StatedSalary:
    low: float
    high: float
    hourly: bool = False
    ranges: int = 1   # more than one usually means pay by location or level; low and high span them all


def _amount(number: str, k: str | None) -> float:
    return float(number.replace(",", "")) * (1000 if k else 1)


def _pay(low: float, high: float, after: str) -> tuple[float, float, bool] | None:
    """A plausible yearly or hourly amount, else None (a stipend, a bonus, a deal size)."""
    hourly = bool(HOURLY_RE.search(after))
    if hourly and 7 <= low <= high <= 500:
        return low, high, True
    if not hourly and 20_000 <= low <= high <= 2_000_000:
        return low, high, False
    return None


def salary_from_text(text: str) -> StatedSalary | None:
    """The pay a posting states: "$150,000—$175,000 USD", "$150k-$175k", "$45 to $60 per
    hour", or one amount on a line about salary. None when there isn't one."""
    found: list[tuple[float, float, bool]] = []
    for m in RANGE_RE.finditer(text or ""):
        low_k, high_k = m.group(2), m.group(4)
        low, high = _amount(m.group(1), low_k), _amount(m.group(3), high_k)
        if high_k and not low_k and low < 1000:  # "$150-175k"
            low *= 1000
        if pay := _pay(low, high, text[m.end():m.end() + 30]):
            found.append(pay)
    if not found:
        for line in (text or "").splitlines():
            if not PAY_WORDS.search(line):
                continue
            for m in SINGLE_RE.finditer(line):
                value = _amount(m.group(1), m.group(2))
                if pay := _pay(value, value, line[m.end():m.end() + 30]):
                    found.append(pay)
    if not found:
        return None
    hourly = found[0][2]
    same_kind = list(dict.fromkeys(p for p in found if p[2] == hourly))
    return StatedSalary(min(p[0] for p in same_kind), max(p[1] for p in same_kind), hourly, len(same_kind))


def pay_text(low: float | None, high: float | None, hourly: bool = False) -> str:
    """Full figures for the detail page: "$150,000–$175,000", "$45–$60.50 an hour",
    "Up to $90,000"."""
    def money(n: float) -> str:
        return f"${n:,.2f}" if n != int(n) else f"${int(n):,}"

    if low and high and round(low) != round(high):
        text = f"{money(low)}–{money(high)}"
    elif low or high:
        text = money(low or high)
        if not (low and high):
            text = f"From {text}" if low else f"Up to {text}"
    else:
        return ""
    return text + (" an hour" if hourly else "")
