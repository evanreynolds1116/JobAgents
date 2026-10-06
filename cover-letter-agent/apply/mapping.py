"""Map a form's fields to your answers (spec: How it works, step 3; What it answers, drafts
or leaves for you).

Claude proposes an answer and a source for every field; code then applies the rules that
don't depend on the model: attestation and consent questions are always left; demographic
and EEO questions are never sent to Claude and are answered only from your
self-identification answers, by code; a choice must be one of the field's real options;
salary is filled only from a saved salary answer; and an answer that can't be found in its
source is marked for your review.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher

from agent import pipeline
from apply import guard, self_id
from apply.extract import Field
from storage import application_profile as app_store
from storage import profile as profile_store
from storage import self_id as self_id_store

SOURCES = ["profile", "application_answers", "saved_answer", "resume", "cover_letter", "none"]
ACTIONS = ["fill", "upload_resume", "upload_cover_letter", "leave"]
LETTER_PLACEHOLDER = "[approved cover letter]"
SALARY = re.compile(r"\b(salary|compensation|pay (range|expectation)|expected pay|desired pay|rate)\b", re.I)
CHOICE_KINDS = ("select", "radio", "checkbox_group", "buttons", "listbox")

SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "action": {"type": "string", "enum": ACTIONS},
                    "value": {"type": "string"},
                    "source": {"type": "string", "enum": SOURCES},
                    "confident": {"type": "boolean"},
                    "note": {"type": "string"},
                },
                "required": ["key", "action", "value", "source", "confident", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["fields"],
    "additionalProperties": False,
}


@dataclass
class Decision:
    key: str
    action: str             # fill, upload_resume, upload_cover_letter or leave
    value: str | list[str]  # a list for fields that take several options
    source: str
    confident: bool
    note: str = ""
    status: str = ""        # filled, review, needs_you or left_for_you (set after filling)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Sources:
    """Everything the agent may use, and nothing else (spec: Guardrails)."""
    profile: profile_store.Profile
    answers: app_store.ApplicationProfile
    saved_answers: list[dict]
    resume_text: str
    letter_text: str = ""       # the approved letter, if there is one
    has_resume_file: bool = True
    self_id: self_id_store.SelfId = field(default_factory=self_id_store.SelfId)  # never sent to Claude

    def blocks(self) -> dict[str, str]:
        p, a = self.profile, self.answers
        profile = {"name": p.name, "email": p.email, "phone": p.phone, "phone_country_code": p.country_code,
                   "city": p.city, "linkedin": p.linkedin, "portfolio": p.portfolio}
        answers = {k: v for k, v in asdict(a).items()}
        saved = [{"question": s["question"], "answer": s["answer"]} for s in self.saved_answers]
        return {"profile": json.dumps(profile, ensure_ascii=False, indent=1),
                "application_answers": json.dumps(answers, ensure_ascii=False, indent=1),
                "saved_answer": json.dumps(saved, ensure_ascii=False, indent=1),
                "resume": self.resume_text}


def _fields_json(fields: list[Field]) -> str:
    # Untrusted page text: stop it from closing the tag.
    data = [{"key": f.key, "kind": f.kind, "label": f.label, "required": f.required, "options": f.options,
             "multiple": f.multiple} for f in fields]
    return re.sub(r"<\s*/?\s*fields\s*>", "[tag removed]", json.dumps(data, ensure_ascii=False, indent=1), flags=re.I)


def ask_claude(client, model: str, fields: list[Field], sources: Sources) -> dict[str, dict]:
    blocks = sources.blocks()
    files = ["resume"] if sources.has_resume_file else []
    if sources.letter_text:
        files.append("cover_letter")
    user = "\n\n".join([
        f"<fields>\n{_fields_json(fields)}\n</fields>",
        f"<profile>\n{blocks['profile']}\n</profile>",
        f"<application_answers>\n{blocks['application_answers']}\n</application_answers>",
        f"<saved_answers>\n{blocks['saved_answer']}\n</saved_answers>",
        f"<resume>\n{blocks['resume']}\n</resume>",
        f"<files>\n{json.dumps(files)}\n</files>",
    ])
    result = pipeline._call_json(client, model, "map", pipeline.load_prompt("map_fields"), user, SCHEMA)
    return {item["key"]: item for item in result["fields"]}


# The rules code enforces -------------------------------------------------------------


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def best_option(value: str, options: list[str]) -> str | None:
    """The option that `value` names: an exact match ignoring case and punctuation, or a
    close one (for example "Yes" for "Yes, I am authorized")."""
    want = _norm(value)
    if not want:
        return None
    for option in options:
        if _norm(option) == want:
            return option
    scored = sorted(((SequenceMatcher(None, want, _norm(o)).ratio(), o) for o in options), reverse=True)
    starts = [o for o in options if _norm(o).startswith(want + " ") or want.startswith(_norm(o) + " ")]
    if len(starts) == 1:
        return starts[0]
    return scored[0][1] if scored and scored[0][0] >= 0.85 else None


def grounded(value: str, source: str, sources: Sources) -> bool:
    """True if the value can be found in the source it claims (digits only for phone-like
    values, so formatting differences don't count against it)."""
    text = sources.blocks().get(source, "")
    if not text or not value:
        return False
    if re.fullmatch(r"[\d\s()+.-]{7,}", value):
        return re.sub(r"\D", "", value)[-7:] in re.sub(r"\D", "", text)
    return _norm(value) in _norm(text)


def leave(key: str, note: str, status: str = "needs_you") -> Decision:
    return Decision(key, "leave", "", "none", False, note, status)


def decide(f: Field, proposal: dict | None, sources: Sources) -> Decision:
    """Claude's proposal for one field, checked against the rules."""
    if guard.is_attestation(f.label):
        return leave(f.key, "Legal attestations and consent are left for you", "left_for_you")
    if guard.is_sensitive(f.label):
        value, note = self_id.answer(f, sources.self_id)
        if value is None:
            return leave(f.key, note, "left_for_you")
        return Decision(f.key, "fill", value, "self_id", True)
    if f.kind == "file" and re.search(r"autofill|auto-fill|parse", f.label, re.I):
        return leave(f.key, "Not used: the agent fills the form itself", "left_for_you")
    if f.kind == "file":
        wants_letter = "cover" in f.label.lower() or (proposal or {}).get("action") == "upload_cover_letter"
        if wants_letter:
            if sources.letter_text:
                return Decision(f.key, "upload_cover_letter", "Cover letter (PDF)", "cover_letter", True)
            return leave(f.key, "No approved cover letter")
        if sources.has_resume_file and (proposal is None or proposal.get("action") != "leave"
                                        or re.search(r"resume|cv", f.label, re.I)):
            return Decision(f.key, "upload_resume", "Resume", "profile", True)
        return leave(f.key, "Not sure what file this wants")
    if f.kind == "checkbox":
        return leave(f.key, "Checkboxes are left for you")
    if not proposal or proposal["action"] != "fill" or not str(proposal["value"]).strip():
        return leave(f.key, (proposal or {}).get("note") or "Nothing in your profile answers this")

    value, source, confident = str(proposal["value"]).strip(), proposal["source"], bool(proposal["confident"])
    if source == "none":
        return leave(f.key, proposal.get("note") or "Nothing in your profile answers this")
    if SALARY.search(f.label) and not sources.answers.salary.strip():
        return leave(f.key, "No saved salary answer")
    if source == "cover_letter" or value == LETTER_PLACEHOLDER:
        if f.kind == "textarea" and sources.letter_text:
            return Decision(f.key, "fill", sources.letter_text, "cover_letter", True)
        return leave(f.key, "No approved cover letter")

    if f.kind in CHOICE_KINDS or (f.kind == "combobox" and f.options):
        wanted = [v.strip() for v in value.split("|")] if f.multiple else [value]
        chosen = [o for o in (best_option(v, f.options) for v in wanted) if o]
        if not chosen:
            return leave(f.key, f"“{value}” isn't one of the options")
        return Decision(f.key, "fill", chosen if f.multiple else chosen[0], source, confident)

    if source in ("profile", "application_answers", "saved_answer", "resume") and not grounded(value, source, sources):
        confident = False  # kept, but highlighted for you to check
    return Decision(f.key, "fill", value, source, confident, proposal.get("note", ""))


def map_fields(client, model: str, fields: list[Field], sources: Sources) -> list[Decision]:
    """A decision for every field. Sensitive fields are never sent to Claude."""
    askable = [f for f in fields if not (guard.is_sensitive(f.label) or guard.is_attestation(f.label))]
    proposals = ask_claude(client, model, askable, sources) if askable else {}
    return [decide(f, proposals.get(f.key), sources) for f in fields]
