"""Drafting pipeline: parse -> match -> draft (Milestone 3); humanize -> verify come in Milestone 4.

Each step is one Claude API call that returns JSON matching a schema (structured
outputs). Prompts live in agent/prompts/. Nothing here can take actions: the
model only returns text, which you review.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic

PROMPTS = Path(__file__).resolve().parent / "prompts"
BANNED_PHRASES = Path(__file__).resolve().parent / "style" / "banned_phrases.txt"

# Server-side fallback: if Claude declines a request, the API retries it on a
# fallback model inside the same call (Claude API only).
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16_000
EFFORT = {"parse": "low", "match": "medium", "draft": "medium"}


class PipelineError(Exception):
    """A step failed. `message` is for you; `raw` holds model output for the debug panel."""

    def __init__(self, message: str, raw: str = ""):
        super().__init__(message)
        self.message = message
        self.raw = raw


# --- Schemas -----------------------------------------------------------------

STR_LIST = {"type": "array", "items": {"type": "string"}}
NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}

PARSE_SCHEMA = {
    "type": "object",
    "properties": {
        "company": NULLABLE_STR,
        "title": NULLABLE_STR,
        "location": NULLABLE_STR,
        "must_have": STR_LIST,
        "nice_to_have": STR_LIST,
        "responsibilities": STR_LIST,
        "keywords": STR_LIST,
        "contact_name": NULLABLE_STR,
        "tone_signals": NULLABLE_STR,
        "several_jobs": {"type": "boolean"},
    },
    "required": ["company", "title", "location", "must_have", "nice_to_have",
                 "responsibilities", "keywords", "contact_name", "tone_signals", "several_jobs"],
    "additionalProperties": False,
}

MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                    "kind": {"type": "string", "enum": ["must_have", "nice_to_have", "responsibility"]},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "quote": {"type": "string"},
                                "source": {"type": "string", "enum": ["resume", "notes"]},
                            },
                            "required": ["quote", "source"],
                            "additionalProperties": False,
                        },
                    },
                    "strength": {"type": "string", "enum": ["strong", "partial", "none"]},
                    "feature": {"type": "boolean"},
                },
                "required": ["requirement", "kind", "evidence", "strength", "feature"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["matches"],
    "additionalProperties": False,
}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {"letter": {"type": "string"}},
    "required": ["letter"],
    "additionalProperties": False,
}


def validate(data, schema, path="$") -> None:
    """Check data against the subset of JSON Schema used above; raises ValueError."""
    if "anyOf" in schema:
        errors = []
        for option in schema["anyOf"]:
            try:
                return validate(data, option, path)
            except ValueError as exc:
                errors.append(str(exc))
        raise ValueError(f"{path}: matches no allowed type ({'; '.join(errors)})")
    kind = schema.get("type")
    checks = {"object": dict, "array": list, "string": str, "boolean": bool}
    if kind == "null":
        if data is not None:
            raise ValueError(f"{path}: expected null")
        return
    if kind in checks and not isinstance(data, checks[kind]):
        raise ValueError(f"{path}: expected {kind}")
    if "enum" in schema and data not in schema["enum"]:
        raise ValueError(f"{path}: {data!r} is not one of {schema['enum']}")
    if kind == "object":
        missing = [k for k in schema.get("required", []) if k not in data]
        if missing:
            raise ValueError(f"{path}: missing {missing}")
        if schema.get("additionalProperties") is False:
            extra = set(data) - set(schema["properties"])
            if extra:
                raise ValueError(f"{path}: unexpected {sorted(extra)}")
        for key, sub in schema["properties"].items():
            if key in data:
                validate(data[key], sub, f"{path}.{key}")
    if kind == "array":
        for i, item in enumerate(data):
            validate(item, schema["items"], f"{path}[{i}]")


# --- Calling Claude ------------------------------------------------------------


def make_client(api_key: str) -> anthropic.Anthropic:
    # The SDK retries connection errors, 408/409/429 and 5xx with exponential backoff.
    return anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=180.0)


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def banned_phrases() -> list[str]:
    lines = BANNED_PHRASES.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def _call_json(client, model: str, step: str, prompt: str, user: str, schema: dict) -> dict:
    """One structured call, retried once if the output doesn't parse or validate."""
    raw = ""
    for attempt in (1, 2):
        raw = _call(client, model, step, prompt, user, schema)
        try:
            data = json.loads(raw)
            validate(data, schema)
            return data
        except ValueError as exc:
            problem = str(exc)
            if attempt == 2:
                raise PipelineError(
                    f"The {step} step returned output that didn't match what the app expects "
                    f"({problem}).", raw=raw,
                ) from exc
    raise AssertionError("unreachable")


def _call(client, model: str, step: str, prompt: str, user: str, schema: dict) -> str:
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=prompt,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": EFFORT[step],
                "format": {"type": "json_schema", "schema": schema},
            },
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as exc:
        raise PipelineError("Claude rejected the API key in .env. Check it's correct and active.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise PipelineError("This API key isn't allowed to use that model.") from exc
    except anthropic.NotFoundError as exc:
        raise PipelineError(f"Claude didn't recognize the model `{model}`. Check ANTHROPIC_MODEL in .env.") from exc
    except anthropic.RateLimitError as exc:
        raise PipelineError("Claude is rate-limiting requests right now. Wait a minute and try again.") from exc
    except anthropic.BadRequestError as exc:
        raise PipelineError(f"Claude couldn't process the request: {exc.message}") from exc
    except anthropic.APIStatusError as exc:
        raise PipelineError(f"Claude had a server problem (HTTP {exc.status_code}) after several tries. Try again shortly.") from exc
    except anthropic.APITimeoutError as exc:
        raise PipelineError("Claude took too long to respond after several tries. Try again.") from exc
    except anthropic.APIConnectionError as exc:
        raise PipelineError("Couldn't reach Claude. Check your internet connection.") from exc

    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    if response.stop_reason == "refusal":
        raise PipelineError(f"Claude declined the {step} step for this posting.", raw=text)
    if response.stop_reason == "max_tokens":
        raise PipelineError(f"The {step} step ran out of room before finishing.", raw=text)
    return text


# --- Steps ---------------------------------------------------------------------


def _posting_block(posting_text: str) -> str:
    # Postings are untrusted: stop them from closing or opening the tag themselves.
    safe = re.sub(r"<\s*/?\s*job_posting\s*>", "[tag removed]", posting_text, flags=re.I)
    return f"<job_posting>\n{safe}\n</job_posting>"


def parse_job(client, model: str, posting_text: str) -> dict:
    """Step 1: posting text -> company, title, requirements and so on."""
    return _call_json(client, model, "parse", load_prompt("parse_job"),
                      _posting_block(posting_text), PARSE_SCHEMA)


def needs_confirmation(parsed: dict) -> bool:
    """No clear company or title, or several jobs on the page: ask you before drafting."""
    return not parsed.get("company") or not parsed.get("title") or bool(parsed.get("several_jobs"))


def match(client, model: str, parsed: dict, resume_text: str, notes: str) -> dict:
    """Step 2: requirements -> exact evidence from the resume and notes."""
    user = (
        f"<job>\n{json.dumps(parsed, indent=2, ensure_ascii=False)}\n</job>\n\n"
        f"<resume>\n{resume_text}\n</resume>\n\n"
        f"<notes>\n{notes.strip() or '(none)'}\n</notes>"
    )
    result = _call_json(client, model, "match", load_prompt("match"), user, MATCH_SCHEMA)
    return check_evidence(result, resume_text, notes)


def _norm(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    return " ".join(text.lower().split())


def check_evidence(result: dict, resume_text: str, notes: str) -> dict:
    """Drop any quote that isn't really in the resume or notes, so invented evidence
    can't reach the draft. Requirements left without evidence become 'none'."""
    sources = {"resume": _norm(resume_text), "notes": _norm(notes)}
    for item in result["matches"]:
        kept, dropped = [], []
        for ev in item["evidence"]:
            quote = _norm(ev["quote"])
            if quote and quote in sources[ev["source"]]:
                kept.append(ev)
            elif quote and quote in sources["resume" if ev["source"] == "notes" else "notes"]:
                kept.append({**ev, "source": "notes" if ev["source"] == "resume" else "resume"})
            else:
                dropped.append(ev["quote"])
        item["evidence"] = kept
        if dropped:
            item["dropped_quotes"] = dropped
        if not kept:
            item["strength"] = "none"
            item["feature"] = False
    featured = [m for m in result["matches"] if m["feature"]]
    order = {"strong": 0, "partial": 1, "none": 2}
    for extra in sorted(featured, key=lambda m: order[m["strength"]])[4:]:
        extra["feature"] = False
    return result


@dataclass
class DraftSettings:
    tone: str
    length: str


def draft(client, model: str, parsed: dict, matches: dict, resume_text: str, notes: str,
          profile, settings: DraftSettings) -> str:
    """Step 3: write the letter (Markdown text)."""
    featured = [m for m in matches["matches"] if m["feature"]]
    others = [m for m in matches["matches"] if not m["feature"]]
    samples = "\n\n---\n\n".join(s[:6000] for s in profile.writing_samples) or "(none provided)"
    profile_block = {
        "name": profile.name or None,
        "sign_off": profile.sign_off or "Thanks for your time,",
        "always_mention": profile.always_mention or None,
        "never_mention": profile.never_mention or None,
    }
    user = "\n\n".join([
        f"<job>\n{json.dumps(parsed, indent=2, ensure_ascii=False)}\n</job>",
        f"<featured_matches>\n{json.dumps(featured, indent=2, ensure_ascii=False)}\n</featured_matches>",
        f"<other_matches>\n{json.dumps(others, indent=2, ensure_ascii=False)}\n</other_matches>",
        f"<resume>\n{resume_text}\n</resume>",
        f"<notes>\n{notes.strip() or '(none)'}\n</notes>",
        f"<profile>\n{json.dumps(profile_block, indent=2, ensure_ascii=False)}\n</profile>",
        f"<writing_samples>\n{samples}\n</writing_samples>",
        f"<settings>\nTone: {settings.tone}\nLength: {settings.length}\n</settings>",
        "<avoid_phrases>\n" + "\n".join(banned_phrases()) + "\n</avoid_phrases>",
    ])
    result = _call_json(client, model, "draft", load_prompt("draft"), user, DRAFT_SCHEMA)
    letter = result["letter"].strip()
    if not letter:
        raise PipelineError("The draft step returned an empty letter.", raw=json.dumps(result))
    return letter


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9'’-]+", text))
