"""Answer demographic and EEO questions from your self-identification answers, with plain
code: nothing here is sent to Claude.

Forms word these options many ways ("I am not a protected veteran", "No, I do not have a
disability and have not had one in the past", "Decline To Self Identify"), so each option is
sorted into a class (man, protected veteran, decline and so on) and the agent picks the one
option in the class that matches your answer. If no option matches, or more than one does,
the question is left for you.
"""

import re

from apply.extract import Field
from storage import self_id as store

CHOICE_KINDS = ("select", "radio", "checkbox_group", "buttons", "listbox", "combobox")

DECLINE = re.compile(r"decline|prefer not|rather not|choose not|not (wish|want) to|don t (wish|want) to|"
                     r"do not (wish|want) to|not to (answer|disclose|say|self|specify|identify)|not disclose|"
                     r"no answer|not specified|undisclosed")
NEGATIVE = re.compile(r"^no\b|\bnot\b|\bnon\b|\bdon t\b|\bnever\b")
POSITIVE = re.compile(r"^yes\b|\bi am\b|\bi have\b|\bi identify\b")

# Which saved answer a question asks for, checked in this order.
CATEGORIES = (
    ("transgender", re.compile(r"transgender", re.I)),
    ("sexual_orientation", re.compile(r"sexual orientation|\bsexuality\b", re.I)),
    ("pronouns", re.compile(r"pronoun", re.I)),
    ("race", re.compile(r"\brace\b|racial", re.I)),
    ("hispanic_latino", re.compile(r"hispanic|latin[oax]", re.I)),
    ("race", re.compile(r"ethnic", re.I)),
    ("veteran", re.compile(r"veteran|armed forces|military", re.I)),
    ("disability", re.compile(r"disabilit", re.I)),
    ("gender", re.compile(r"gender|\bsex\b", re.I)),
)

GENDER_CLASSES = (("Non-binary", r"non ?binary|genderqueer|gender non ?conforming|gender ?fluid"),
                  ("Woman", r"\b(female|woman|women)\b"), ("Man", r"\b(male|man|men)\b"))
ORIENTATION_CLASSES = (("Heterosexual or straight", r"straight|heterosexual"), ("Gay", r"\bgay\b"),
                       ("Lesbian", r"lesbian"), ("Bisexual", r"\bbi ?sexual\b"), ("Pansexual", r"pansexual"),
                       ("Queer", r"\bqueer\b"), ("Asexual", r"\basexual\b"))
RACE_CLASSES = (("American Indian or Alaska Native", r"american indian|alaska(n)? native|native american|indigenous"),
                ("Asian", r"\basian\b"), ("Black or African American", r"\bblack\b|african american"),
                ("Hispanic or Latino", r"hispanic|latin[oax]"),
                ("Middle Eastern or North African", r"middle eastern|north african"),
                ("Native Hawaiian or Other Pacific Islander", r"hawaiian|pacific islander"),
                ("White", r"\bwhite\b"), ("Two or more races", r"two or more|multi ?racial|more than one"))

# Veteran answers, with the option classes to try in order.
VETERAN_PREFERENCE = {"Not a veteran": ("not_veteran", "not_protected"),
                      "Protected veteran": ("protected", "veteran"),
                      "Veteran, not protected": ("not_protected", "veteran")}


def _main(option: str) -> str:
    """The option's name without explanations: "White (Not Hispanic or Latino)" and "White -
    A person having origins in ... the Middle East" both become "white"."""
    head = re.split(r"\s[-–—]\s|:|\(", str(option), maxsplit=1)[0]
    return re.sub(r"[^a-z0-9]+", " ", (head or str(option)).lower()).strip()


def category(label: str) -> str | None:
    for name, pattern in CATEGORIES:
        if pattern.search(label or ""):
            return name
    return None


def _yes_no(text: str) -> str | None:
    if DECLINE.search(text):
        return store.DECLINE
    if NEGATIVE.search(text):
        return "No"
    if POSITIVE.search(text):
        return "Yes"
    return None


def classes(name: str, option: str, label: str = "") -> set[str]:
    """The classes one option belongs to, for the question `name`."""
    text = _main(option)
    if DECLINE.search(text):
        return {store.DECLINE}
    if name in ("gender", "sexual_orientation", "race"):
        table = {"gender": GENDER_CLASSES, "sexual_orientation": ORIENTATION_CLASSES, "race": RACE_CLASSES}[name]
        return {cls for cls, pattern in table if re.search(pattern, text)}
    if name == "hispanic_latino":
        if NEGATIVE.search(text):
            return {"No"}
        return {"Yes"} if re.search(r"^yes\b|hispanic|latin[oax]", text) else set()
    if name == "veteran":
        protected = "protected" in label.lower()
        if re.fullmatch(r"yes", text):
            return {"protected" if protected else "veteran"}
        if re.fullmatch(r"no", text):
            return {"not_protected" if protected else "not_veteran"}
        if not re.search(r"veteran|served|military|classification", text):
            return set()
        is_protected = bool(re.search(r"protected|classification", text))
        if NEGATIVE.search(text):
            return {"not_protected" if is_protected else "not_veteran"}
        return {"protected" if is_protected else "veteran"}
    answer = _yes_no(text)
    return {answer} if answer else set()


def pick(name: str, answer: str, options: list[str], label: str = "", hispanic: str = "") -> str | None:
    """The one option matching your answer, or None if none or several do. `hispanic` is your
    Hispanic or Latino answer, for an "Ethnicity" question that only asks that."""
    if not answer or not options:
        return None
    wanted = VETERAN_PREFERENCE.get(answer, (answer,)) if name == "veteran" else (answer,)
    if name == "race" and answer != store.DECLINE and \
            all(classes(name, o) <= {"Hispanic or Latino", store.DECLINE} for o in options):
        name, wanted = "hispanic_latino", ("Yes",) if answer == "Hispanic or Latino" else (hispanic,)
    for cls in wanted:
        matches = [o for o in options if cls in classes(name, o, label)]
        if len(matches) == 1:
            return matches[0]
        if matches:
            return None
    return None


def answer(f: Field, answers: store.SelfId) -> tuple[str | list[str] | None, str]:
    """The value to enter for a demographic field, or None and a note saying why not."""
    name = category(f.label)
    if name is None:
        return None, "The agent only answers these from your self-identification answers"
    saved = getattr(answers, name)
    if not saved.strip():
        return None, "Not set in your self-identification answers"
    if name == "pronouns" and f.kind in ("text", "textarea"):
        return saved.strip(), ""
    if f.kind not in CHOICE_KINDS or not f.options:
        return None, "The agent only picks from a list of options for these"
    if name == "pronouns":
        want = re.sub(r"[^a-z]+", " ", saved.lower()).split()
        chosen = [o for o in f.options if re.sub(r"[^a-z]+", " ", o.lower()).split()[:len(want)] == want]
        option = chosen[0] if len(chosen) == 1 else None
    else:
        option = pick(name, saved, f.options, f.label, answers.hispanic_latino)
    if option is None:
        return None, f"Your answer “{saved}” doesn't match one option here"
    return ([option] if f.multiple else option), ""
