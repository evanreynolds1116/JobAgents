"""Application profile: standard answers for job application forms, stored in
data/application_profile.yaml (spec: Data & storage; Phase 2, Milestone 6).

The application agent (Milestones 7 and 8) fills these into forms. A blank answer means
"not set": the agent leaves that question for you instead of guessing. Contact details
(name, email, phone, links) come from profile.yaml.
"""

from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml

import config

YES_NO = ("", "Yes", "No")
RELOCATION = ("", "Open to it", "Yes", "No")


@dataclass
class ApplicationProfile:
    street: str = ""
    street2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = "United States"
    work_authorized: str = ""      # Authorized to work in the US: Yes / No
    needs_sponsorship: str = ""    # Now or in the future: Yes / No
    relocation: str = ""           # Willing to relocate: Open to it / Yes / No
    start_date: str = ""           # e.g. "Two weeks after an offer"
    salary: str = ""               # optional; blank means you answer it yourself each time
    heard_about: str = ""          # how you usually hear about jobs, e.g. "Company website"

    def problems(self) -> list[str]:
        """Light checks shown as warnings; saving still works."""
        found = []
        if self.work_authorized == "No" and self.needs_sponsorship == "No":
            found.append("You said you're not authorized to work in the US and don't need sponsorship. "
                         "Check those two answers.")
        if self.postal_code and self.country in ("United States", "US", "USA") \
                and not (self.postal_code.replace("-", "").isdigit() and len(self.postal_code) in (5, 10)):
            found.append("The ZIP code should look like 37203 or 37203-1234.")
        return found


def path() -> Path:
    return config.DATA_DIR / "application_profile.yaml"


def load() -> ApplicationProfile:
    file = path()
    if not file.exists():
        return ApplicationProfile()
    raw = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    known = {f.name for f in fields(ApplicationProfile)}
    # A hand-edited file may have Yes/No unquoted, which YAML reads as true/false.
    values = {k: ("Yes" if v else "No") if isinstance(v, bool) else str(v)
              for k, v in raw.items() if k in known and v is not None}
    profile = ApplicationProfile(**values)
    for name, allowed in (("work_authorized", YES_NO), ("needs_sponsorship", YES_NO), ("relocation", RELOCATION)):
        if getattr(profile, name) not in allowed:
            setattr(profile, name, "")
    return profile


def save(profile: ApplicationProfile) -> None:
    data = {k: v.strip() for k, v in asdict(profile).items()}
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".yaml.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(file)
