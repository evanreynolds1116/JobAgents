"""Claude's work-setting label and fit score for new postings (spec: How a search run works,
step 6; Milestone 11).

One call reads up to BATCH postings with your resume and returns, for each one, the work
setting, a fit score from 1 to 5 and a one-line reason. Batches run a few at a time. Only
new postings are scored; jobs already in the app keep their score.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import config
from agent import pipeline
from search.normalize import Job
from storage import resume

BATCH = 10
WORKERS = 4
MAX_CHARS = 3000  # watch-list jobs come with full descriptions; the start is enough to score

SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "work_setting": {"type": "string", "enum": ["remote", "hybrid", "onsite", "unknown"]},
                    "fit": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                    "reason": {"type": "string"},
                },
                "required": ["id", "work_setting", "fit", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["jobs"],
    "additionalProperties": False,
}


@dataclass
class Score:
    work_setting: str
    fit: int
    reason: str


def _postings_block(jobs: list[Job]) -> str:
    parts = []
    for n, job in enumerate(jobs, 1):
        text = (f"Title: {job.title}\nCompany: {job.company}\nLocation: {job.location or 'not given'}\n\n"
                f"{job.description[:MAX_CHARS]}")
        # Postings are untrusted: stop them from closing or opening the tags themselves.
        safe = re.sub(r"<\s*/?\s*postings?\b[^>]*>", "[tag removed]", text, flags=re.I)
        parts.append(f'<posting id="{n}">\n{safe}\n</posting>')
    return "<postings>\n" + "\n\n".join(parts) + "\n</postings>"


def score_batch(client, model: str, jobs: list[Job], resume_text: str) -> list[Score]:
    """One call for up to BATCH postings; scores come back in the same order."""
    user = f"<resume>\n{resume_text}\n</resume>\n\n{_postings_block(jobs)}"
    result = pipeline._call_json(client, model, "score", pipeline.load_prompt("score_jobs"), user, SCHEMA)
    by_id = {item["id"].strip(): item for item in result["jobs"]}
    ids = [str(n) for n in range(1, len(jobs) + 1)]
    if missing := [i for i in ids if i not in by_id]:
        raise pipeline.PipelineError(f"The fit step skipped posting{'s' if len(missing) > 1 else ''} "
                                     f"{', '.join(missing)}.", raw=json.dumps(result))
    return [Score(by_id[i]["work_setting"], by_id[i]["fit"], by_id[i]["reason"].strip()) for i in ids]


def score_jobs(jobs: list[Job]) -> tuple[list[Score | None], list[str]]:
    """Scores for `jobs`, in order, and any problems to show. A posting whose batch failed
    gets None: it's kept with the setting read from its text and no fit score."""
    if not jobs:
        return [], []
    settings = config.load_settings()
    if settings.key_status != "ok":
        return [None] * len(jobs), ["Fit scores skipped: add a valid ANTHROPIC_API_KEY to .env."]
    resume_text = resume.load_text()
    if not resume_text.strip():
        return [None] * len(jobs), ["Fit scores skipped: add your resume on Profile & resume first."]
    client = pipeline.make_client(settings.api_key)

    def one(batch: list[Job]) -> tuple[list[Score | None], str | None]:
        try:
            return score_batch(client, settings.model, batch, resume_text), None
        except pipeline.PipelineError as exc:
            return [None] * len(batch), str(exc)

    batches = [jobs[i:i + BATCH] for i in range(0, len(jobs), BATCH)]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(one, batches))
    scores = [s for batch_scores, _ in results for s in batch_scores]
    failed = sum(len(b) for b, (_, error) in zip(batches, results) if error)
    errors = [f"Fit scores failed for {failed} posting{'s' if failed != 1 else ''}: {error}"
              for error in dict.fromkeys(e for _, e in results if e)]
    return scores, errors
