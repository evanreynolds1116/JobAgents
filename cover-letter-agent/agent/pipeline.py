"""Drafting pipeline: parse -> match -> draft -> humanize -> verify.

Each step is one Claude API call that returns JSON matching a schema (structured
outputs). Prompts live in agent/prompts/. Nothing here can take actions: the
model only returns text, which you review.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic

from agent import lint

PROMPTS = Path(__file__).resolve().parent / "prompts"

# Server-side fallback: if Claude declines a request, the API retries it on a
# fallback model inside the same call (Claude API only).
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16_000
EFFORT = {"parse": "low", "match": "low", "draft": "medium", "humanize": "low", "verify": "medium",
          "fix": "low", "trim": "low"}


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
        if "credit balance" in str(exc.message).lower():
            raise PipelineError(
                "Your Anthropic account is out of API credits. Add credits at "
                "console.anthropic.com under Settings → Billing, then try again."
            ) from exc
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
    """Letters and digits only, lowercased. Quotes are compared this way so that line
    breaks, hyphenation and punctuation from PDF conversion ("sealed-\\nbid") don't make
    a real quote look invented; invented words still won't be found."""
    return re.sub(r"[\W_]+", "", text.lower())


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

    @property
    def word_limits(self) -> tuple[int, int]:
        return word_limits(self.length)


def word_limits(length: str) -> tuple[int, int]:
    """(fewest, most) words for a length setting: "250–400 words" or "Short, under 250 words"."""
    return (150, 250) if length.startswith("Short") else (250, 400)


def _samples(profile) -> str:
    return "\n\n---\n\n".join(s[:6000] for s in profile.writing_samples) or "(none provided)"


def draft(client, model: str, parsed: dict, matches: dict, resume_text: str, notes: str,
          profile, settings: DraftSettings, previous: str | None = None,
          feedback: str | None = None) -> str:
    """Step 3: write the letter (Markdown text), or revise `previous` to follow `feedback`."""
    featured = [m for m in matches["matches"] if m["feature"]]
    others = [m for m in matches["matches"] if not m["feature"]]
    samples = _samples(profile)
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
        "<avoid_phrases>\n" + "\n".join(lint.load_phrases()) + "\n</avoid_phrases>",
    ])
    if previous and feedback:
        user += f"\n\n<previous_draft>\n{previous}\n</previous_draft>\n\n<feedback>\n{feedback}\n</feedback>"
    result = _call_json(client, model, "draft", load_prompt("draft"), user, DRAFT_SCHEMA)
    letter = result["letter"].strip()
    if not letter:
        raise PipelineError("The draft step returned an empty letter.", raw=json.dumps(result))
    return letter


# --- Step 4: humanize ------------------------------------------------------------

HUMANIZE_SCHEMA = {
    "type": "object",
    "properties": {"letter": {"type": "string"}, "changes": STR_LIST},
    "required": ["letter", "changes"],
    "additionalProperties": False,
}


def humanize(client, model: str, letter: str, profile, settings: DraftSettings) -> tuple[str, list[str]]:
    """Step 4: reword linter hits and stiff sentences without adding facts."""
    hits = lint.lint(letter)
    flagged = "\n".join(f"- {h.text}: {h.message}" for h in hits) or "(nothing flagged by the linter)"
    user = "\n\n".join([
        f"<letter>\n{letter}\n</letter>",
        f"<flagged>\n{flagged}\n</flagged>",
        f"<writing_samples>\n{_samples(profile)}\n</writing_samples>",
        f"<settings>\nTone: {settings.tone}\nLength: {settings.length}\n"
        f"Word limit: {settings.word_limits[1]}\n</settings>",
    ])
    result = _call_json(client, model, "humanize", load_prompt("humanize"), user, HUMANIZE_SCHEMA)
    revised = result["letter"].strip()
    return (revised or letter), result["changes"]


# --- Step 5: verify --------------------------------------------------------------

SOURCES = ["resume", "profile", "notes", "posting", "none"]
VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "supported": {"type": "boolean"},
                    "source": {"type": "string", "enum": SOURCES},
                    "evidence": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["claim", "supported", "source", "evidence", "reason"],
                "additionalProperties": False,
            },
        },
        "style_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "issue": {"type": "string"}},
                "required": ["text", "issue"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["claims", "style_flags"],
    "additionalProperties": False,
}


def profile_text(profile) -> str:
    """The profile facts a letter may use, as plain text for checking claims."""
    lines = [
        f"Name: {profile.name}" if profile.name else "",
        f"Email: {profile.email}" if profile.email else "",
        f"Phone: {profile.country_code} {profile.phone}" if profile.phone else "",
        f"City: {profile.city}" if profile.city else "",
        f"LinkedIn: {profile.linkedin}" if profile.linkedin else "",
        f"Portfolio: {profile.portfolio}" if profile.portfolio else "",
        f"Always mention: {profile.always_mention}" if profile.always_mention else "",
    ]
    return "\n".join(line for line in lines if line) or "(empty)"


def verify(client, model: str, letter: str, resume_text: str, profile, notes: str,
           posting_text: str) -> dict:
    """Step 5: list every claim with its source; flag unsupported claims and style issues."""
    sources = {"resume": resume_text, "profile": profile_text(profile), "notes": notes or "",
               "posting": posting_text}
    user = "\n\n".join([
        f"<letter>\n{letter}\n</letter>",
        f"<resume>\n{resume_text}\n</resume>",
        f"<profile>\n{sources['profile']}\n</profile>",
        f"<notes>\n{notes.strip() or '(none)'}\n</notes>",
        _posting_block(posting_text),
    ])
    result = _call_json(client, model, "verify", load_prompt("verify"), user, VERIFY_SCHEMA)
    return check_claims(result, letter, sources)


def check_claims(result: dict, letter: str, sources: dict[str, str]) -> dict:
    """Code checks on the verifier: a 'supported' claim needs a quote that is really in
    its source, and each flag is located in the letter for highlighting."""
    normalized = {name: _norm(text) for name, text in sources.items()}
    letter_norm = _norm(letter)
    for c in result["claims"]:
        if c["supported"]:
            quote = _norm(c["evidence"])
            if not quote or c["source"] not in normalized or quote not in normalized[c["source"]]:
                c["supported"] = False
                c["reason"] = (f"The supporting quote couldn't be found in your {c['source']}, "
                               "so this needs your check.")
        c["in_letter"] = _norm(c["claim"]) in letter_norm
    for f in result["style_flags"]:
        f["in_letter"] = _norm(f["text"]) in letter_norm
    result["lint"] = [h.to_dict() for h in lint.lint(letter)]
    return result


# --- Fix-up pass (after step 5) ----------------------------------------------------

FIX_SCHEMA = HUMANIZE_SCHEMA  # {"letter": ..., "changes": [...]}


def fix_claims(client, model: str, letter: str, verify_result: dict, resume_text: str, profile,
               notes: str, posting_text: str, max_words: int | None = None) -> tuple[str, list[str]]:
    """Rewrite or remove the claims verify flagged, changing nothing else. Run once, then
    verify again; anything still unsupported stays flagged for you."""
    unsupported = flags(verify_result)["claims"]
    if not unsupported:
        return letter, []
    listed = "\n".join(f'- "{c["claim"]}"\n  Why: {c["reason"] or "No source supports it."}' for c in unsupported)
    user = "\n\n".join([
        f"<letter>\n{letter}\n</letter>",
        f"<flagged_claims>\n{listed}\n</flagged_claims>",
        f"<resume>\n{resume_text}\n</resume>",
        f"<profile>\n{profile_text(profile)}\n</profile>",
        f"<notes>\n{notes.strip() or '(none)'}\n</notes>",
        _posting_block(posting_text),
    ])
    if max_words:
        user += f"\n\n<word_limit>{max_words}</word_limit>"
    result = _call_json(client, model, "fix", load_prompt("fix_claims"), user, FIX_SCHEMA)
    fixed = result["letter"].strip()
    return (fixed or letter), result["changes"]


# --- Trim (after humanize or the fix-up, only when over the limit) ---------------

TRIM_MARGIN = 20  # aim this many words under the limit, so the count lands inside it


def trim(client, model: str, letter: str, max_words: int) -> tuple[str, list[str]]:
    """Cut a letter that went over the word limit, removing words and adding nothing.
    No call when it's already within the limit. Verify runs afterwards as usual."""
    words = word_count(letter)
    if words <= max_words:
        return letter, []
    user = "\n\n".join([
        f"<letter>\n{letter}\n</letter>",
        f"<word_count>{words}</word_count>",
        f"<target>{max_words - TRIM_MARGIN} to {max_words} words</target>",
    ])
    result = _call_json(client, model, "trim", load_prompt("trim"), user, FIX_SCHEMA)
    trimmed = result["letter"].strip()
    return (trimmed or letter), result["changes"]


def flags(verify_result: dict | None) -> dict:
    """What needs your review before approving: unsupported claims, style flags, linter hits."""
    if not verify_result:
        return {"claims": [], "style": [], "lint": [], "unchecked": True}
    return {
        "claims": [c for c in verify_result["claims"] if not c["supported"]],
        "style": verify_result.get("style_flags", []),
        "lint": verify_result.get("lint", []),
        "unchecked": False,
    }


def flag_count(verify_result: dict | None) -> int:
    f = flags(verify_result)
    return len(f["claims"]) + len(f["style"]) + len(f["lint"])


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9'’-]+", text))
