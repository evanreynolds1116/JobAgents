"""Drafted answers to short screening questions (spec: What it answers, drafts or leaves
for you; Milestone 8).

Open questions the mapping left blank ("Why do you want to work here?") are drafted in one
Claude call per page, with the cover letter's style rules and banned phrases, from your
resume, profile, notes, the saved posting and the approved letter. Every draft is
highlighted for your review; a question the sources can't honestly answer stays blank.
"""

import json
import re

from agent import lint, pipeline
from apply import guard
from apply.extract import Field
from apply.mapping import SALARY, Decision, Sources

QUESTION = re.compile(r"\?\s*$|^(why|what|how|describe|tell us|share|explain|please (describe|explain|tell|share))\b",
                      re.I)
NOT_QUESTIONS = re.compile(r"\b(additional information|anything else|comments|cover letter|website|url|"
                           r"portfolio|github|linkedin|address|name|email|phone|city|zip|postal)\b", re.I)

SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"key": {"type": "string"}, "answer": {"type": "string"}},
                "required": ["key", "answer"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answers"],
    "additionalProperties": False,
}


def is_screening_question(f: Field, d: Decision) -> bool:
    """A free-text question the mapping left blank and the agent may draft."""
    return (d.action == "leave" and d.status == "needs_you" and f.kind in ("text", "textarea")
            and bool(QUESTION.search(f.label.strip())) and not NOT_QUESTIONS.search(f.label)
            and not SALARY.search(f.label) and not guard.is_sensitive(f.label) and not guard.is_attestation(f.label))


def _safe(text: str, tag: str) -> str:
    return re.sub(rf"<\s*/?\s*{tag}\s*>", "[tag removed]", text or "", flags=re.I)


def draft_answers(client, model: str, questions: list[Field], sources: Sources, posting_text: str,
                  notes: str, writing_samples: list[str]) -> dict[str, str]:
    """Drafts keyed by field key; empty for questions left to you."""
    if not questions:
        return {}
    listed = [{"key": f.key, "question": f.label, "kind": f.kind} for f in questions]
    blocks = sources.blocks()
    user = "\n\n".join([
        f"<questions>\n{_safe(json.dumps(listed, ensure_ascii=False, indent=1), 'questions')}\n</questions>",
        f"<resume>\n{sources.resume_text}\n</resume>",
        f"<profile>\n{blocks['profile']}\n</profile>",
        f"<notes>\n{notes.strip() or '(none)'}\n</notes>",
        f"<cover_letter>\n{sources.letter_text or '(none)'}\n</cover_letter>",
        f"<job_posting>\n{_safe(posting_text, 'job_posting')}\n</job_posting>",
        "<writing_samples>\n" + ("\n\n---\n\n".join(s[:6000] for s in writing_samples) or "(none provided)")
        + "\n</writing_samples>",
        "<avoid_phrases>\n" + "\n".join(lint.load_phrases()) + "\n</avoid_phrases>",
    ])
    result = pipeline._call_json(client, model, "screen", pipeline.load_prompt("screening"), user, SCHEMA)
    return {item["key"]: item["answer"].strip() for item in result["answers"]}


def apply_drafts(fields: list[Field], decisions: list[Decision], drafts: dict[str, str]) -> list[Decision]:
    """Turn drafts into fill decisions, always marked for review, with any linter hits noted."""
    by_key = {f.key: f for f in fields}
    out = []
    for d in decisions:
        text = drafts.get(d.key, "")
        if text and is_screening_question(by_key[d.key], d):
            hits = lint.lint(text)
            note = "Drafted for you; check it" + (f" ({len(hits)} style flag{'s' if len(hits) != 1 else ''})"
                                                   if hits else "")
            d = Decision(d.key, "fill", text, "drafted", False, note)
        out.append(d)
    return out
