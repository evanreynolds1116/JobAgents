"""Saved search criteria (spec: Phase 3, Search criteria)."""

from dataclasses import asdict, dataclass, field

from search import places

SETTINGS = ("remote", "hybrid", "onsite")
SETTING_LABELS = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site", "unknown": "Unknown"}
DATE_OPTIONS = {1: "Last 24 hours", 3: "Last 3 days", 7: "Last week"}
MILES_TO_KM = 1.609344


@dataclass
class City:
    name: str           # "Nashville, TN"
    radius_miles: int = 25

    @property
    def radius_km(self) -> int:
        return round(self.radius_miles * MILES_TO_KM)


@dataclass
class SearchCriteria:
    titles: list[str] = field(default_factory=list)
    cities: list[City] = field(default_factory=list)
    settings: list[str] = field(default_factory=lambda: ["remote", "hybrid"])
    salary_min: int | None = None
    salary_max: int | None = None
    max_days_old: int = 3
    exclude_companies: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SearchCriteria":
        data = dict(data)
        data["cities"] = [City(**c) for c in data.get("cities", [])]
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def problems(self) -> list[str]:
        found = []
        if not [t for t in self.titles if t.strip()]:
            found.append("Add at least one job title.")
        if not self.settings:
            found.append("Pick at least one work setting.")
        if set(self.settings) & {"hybrid", "onsite"} and not self.cities:
            found.append("Hybrid and on-site jobs need at least one city.")
        for city in self.cities:
            if not places.lookup(city.name):
                found.append(f"Couldn't find \"{city.name}\" in the list of U.S. cities. "
                             "Type it as city, state, for example Nashville, TN.")
        if self.salary_min and self.salary_max and self.salary_min > self.salary_max:
            found.append("The minimum salary is higher than the maximum.")
        if self.max_days_old not in DATE_OPTIONS:
            found.append("Pick last 24 hours, last 3 days or last week.")
        return found

    def summary(self) -> list[tuple[str, str]]:
        """Label and value pairs for the saved-search card."""
        rows = [("Titles", ", ".join(self.titles))]
        local = [SETTING_LABELS[s] for s in ("hybrid", "onsite") if s in self.settings]
        if local:
            near = "; ".join(f"{c.name} ({c.radius_miles} mi)" for c in self.cities)
            rows.append((" and ".join(local), f"near {near}"))
        if "remote" in self.settings:
            rows.append(("Remote", "Anywhere in the US"))
        if self.salary_min or self.salary_max:
            low = f"${self.salary_min // 1000}k" if self.salary_min else "any"
            high = f"${self.salary_max // 1000}k" if self.salary_max else "any"
            rows.append(("Salary", f"{low}–{high}"))
        rows.append(("Posted", DATE_OPTIONS[self.max_days_old]))
        excluded = self.exclude_companies + self.exclude_keywords
        if excluded:
            rows.append(("Excluding", ", ".join(excluded)))
        return rows
