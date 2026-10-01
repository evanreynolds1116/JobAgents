"""Your profile, stored in data/profile.yaml (spec: Data & storage).

The YAML is written with block-style multi-line text so it stays readable if you
open it in an editor.
"""

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
    phone: str = ""
    city: str = ""
    link: str = ""  # LinkedIn or portfolio URL
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
        if self.link and not self.link.startswith(("http://", "https://")):
            found.append("The LinkedIn or portfolio link should start with https://")
        return found


def profile_path() -> Path:
    return config.DATA_DIR / "profile.yaml"


def load() -> Profile:
    path = profile_path()
    if not path.exists():
        return Profile()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    known = {f.name for f in fields(Profile)}
    values = {k: v for k, v in raw.items() if k in known and v is not None}
    if "writing_samples" in values:
        values["writing_samples"] = [str(s) for s in values["writing_samples"] if str(s).strip()]
    for key, value in values.items():
        if key != "writing_samples":
            values[key] = str(value)
    profile = Profile(**values)
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
