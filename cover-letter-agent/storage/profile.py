"""Your profile, stored in data/profile.yaml (spec: Data & storage).

The YAML is written with block-style multi-line text so it stays readable if you
open it in an editor.
"""

import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

import config

TONES = ("Professional and warm", "More formal", "More casual")
LENGTHS = ("250–400 words", "Short, under 250 words")


@dataclass
class Profile:
    name: str = ""
    email: str = ""
    country_code: str = "+1"  # phone country calling code
    phone: str = ""
    city: str = ""
    linkedin: str = ""
    portfolio: str = ""
    tone: str = TONES[0]
    length: str = LENGTHS[0]
    sign_off: str = "Thanks for your time,"
    always_mention: str = ""
    never_mention: str = ""
    writing_samples: list[str] = field(default_factory=list)

    def problems(self) -> list[str]:
        """Light checks shown as warnings; saving still works."""
        found = []
        if self.email and ("@" not in self.email or " " in self.email.strip()):
            found.append("The email address doesn't look complete.")
        code = normalize_country_code(self.country_code)
        if code and not re.fullmatch(r"\+\d{1,4}", code):
            found.append("The country code should look like +1 or +44.")
        for label, url in (("LinkedIn", self.linkedin), ("portfolio", self.portfolio)):
            if url and not url.startswith(("http://", "https://")):
                found.append(f"The {label} link should start with https://")
        if self.linkedin and "linkedin.com" not in self.linkedin.lower():
            found.append("The LinkedIn link doesn't look like a linkedin.com address.")
        return found


def normalize_country_code(code: str) -> str:
    """'1', ' +1 ' and '+1' all become '+1'."""
    code = str(code).strip().replace(" ", "")
    return f"+{code}" if code.isdigit() else code


def profile_path() -> Path:
    return config.DATA_DIR / "profile.yaml"


def load() -> Profile:
    path = profile_path()
    if not path.exists():
        return Profile()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # Earlier versions had one "link" field for LinkedIn or portfolio.
    old_link = str(raw.pop("link", "") or "").strip()
    if old_link:
        target = "linkedin" if "linkedin.com" in old_link.lower() else "portfolio"
        raw.setdefault(target, old_link)
    known = {f.name for f in fields(Profile)}
    values = {k: v for k, v in raw.items() if k in known and v is not None}
    if "writing_samples" in values:
        values["writing_samples"] = [str(s) for s in values["writing_samples"] if str(s).strip()]
    for key, value in values.items():
        if key != "writing_samples":
            values[key] = str(value)
    profile = Profile(**values)
    profile.country_code = normalize_country_code(profile.country_code)  # YAML reads +1 as 1
    if profile.tone not in TONES:
        profile.tone = TONES[0]
    if profile.length not in LENGTHS:
        profile.length = LENGTHS[0]
    return profile


def save(profile: Profile) -> None:
    data = asdict(profile)
    for key, value in data.items():
        if isinstance(value, str):
            data[key] = value.strip()
    data["country_code"] = normalize_country_code(profile.country_code)
    data["writing_samples"] = [s.strip() for s in profile.writing_samples if s.strip()]
    text = yaml.dump(data, Dumper=_BlockDumper, sort_keys=False, allow_unicode=True, width=1000)
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


class _BlockDumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_BlockDumper.add_representer(str, _str_presenter)
