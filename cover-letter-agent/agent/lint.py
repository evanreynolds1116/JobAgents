"""Phrase linter: code checks for wording that sounds machine-written.

Checks the editable list in agent/style/banned_phrases.txt (case-insensitive)
plus two style rules from the spec: at most one em dash per letter, and no
"I am writing to express my interest" opener.
"""

import re
from dataclasses import asdict, dataclass
from pathlib import Path

BANNED_PHRASES = Path(__file__).resolve().parent / "style" / "banned_phrases.txt"
GENERIC_OPENERS = (
    r"I am writing to express my (?:strong |keen )?interest",
    r"I am writing to apply",
    r"I'm writing to express my (?:strong |keen )?interest",
)


@dataclass
class Hit:
    kind: str      # "phrase", "em_dash" or "opener"
    text: str      # the exact text in the letter
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def load_phrases(path: Path | None = None) -> list[str]:
    lines = (path or BANNED_PHRASES).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def save_phrases(phrases: list[str], path: Path | None = None) -> None:
    path = path or BANNED_PHRASES
    header = "# One phrase per line, matched case-insensitively. Lines starting with # are ignored.\n"
    unique = list(dict.fromkeys(p.strip() for p in phrases if p.strip()))
    path.write_text(header + "\n".join(unique) + "\n", encoding="utf-8")


def _straight(text: str) -> str:
    # Same length as the input, so match positions still line up with the letter.
    return text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')


def lint(letter: str, phrases: list[str] | None = None) -> list[Hit]:
    phrases = load_phrases() if phrases is None else phrases
    plain = _straight(letter)
    hits: list[Hit] = []
    for phrase in phrases:
        # Word boundary at the start only, so "leverage" also catches "leveraged".
        pattern = r"(?<![\w])" + re.escape(_straight(phrase))
        for m in re.finditer(pattern, plain, flags=re.IGNORECASE):
            hits.append(Hit("phrase", letter[m.start():m.end()], f'"{phrase}" is on your banned-phrase list.'))
    dashes = letter.count("—")
    if dashes > 1:
        hits.append(Hit("em_dash", "—", f"{dashes} em dashes. Your style rules allow one per letter."))
    for opener in GENERIC_OPENERS:
        for m in re.finditer(opener, plain, flags=re.IGNORECASE):
            hits.append(Hit("opener", letter[m.start():m.end()], "Generic opener. Start with something specific to this company or role."))
    return hits
