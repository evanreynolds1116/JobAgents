"""Self-identification answers for demographic and EEO questions (gender, race, veteran
status, disability and the like), stored in data/self_id.yaml.

Kept apart from the application answers on purpose: these are never sent to Claude. The
application agent matches them to a form's options with plain code (apply/self_id.py).
A blank answer means "not set": the agent leaves that question for you.
"""

from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml

import config

DECLINE = "Decline to self-identify"
YES_NO = ("", "Yes", "No", DECLINE)
GENDER = ("", "Man", "Woman", "Non-binary", DECLINE)
ORIENTATION = ("", "Heterosexual or straight", "Gay", "Lesbian", "Bisexual", "Pansexual", "Queer", "Asexual",
               DECLINE)
RACE = ("", "American Indian or Alaska Native", "Asian", "Black or African American", "Hispanic or Latino",
        "Middle Eastern or North African", "Native Hawaiian or Other Pacific Islander", "White",
        "Two or more races", DECLINE)
VETERAN = ("", "Not a veteran", "Protected veteran", "Veteran, not protected", DECLINE)
CHOICES = {"gender": GENDER, "transgender": YES_NO, "sexual_orientation": ORIENTATION, "race": RACE,
           "hispanic_latino": YES_NO, "veteran": VETERAN, "disability": YES_NO}


@dataclass
class SelfId:
    gender: str = ""
    transgender: str = ""
    sexual_orientation: str = ""
    race: str = ""
    hispanic_latino: str = ""
    veteran: str = ""
    disability: str = ""
    pronouns: str = ""   # free text, e.g. "she/her"


def path() -> Path:
    return config.DATA_DIR / "self_id.yaml"


def load() -> SelfId:
    file = path()
    if not file.exists():
        return SelfId()
    raw = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    known = {f.name for f in fields(SelfId)}
    values = {k: ("Yes" if v else "No") if isinstance(v, bool) else str(v)
              for k, v in raw.items() if k in known and v is not None}
    answers = SelfId(**values)
    for name, allowed in CHOICES.items():
        if getattr(answers, name) not in allowed:
            setattr(answers, name, "")
    return answers


def save(answers: SelfId) -> None:
    data = {k: v.strip() for k, v in asdict(answers).items()}
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".yaml.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(file)
