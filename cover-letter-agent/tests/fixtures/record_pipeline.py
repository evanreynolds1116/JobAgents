r"""Record real Claude responses for tests/test_pipeline.py, so tests replay them for free.

Uses your API key and costs a few cents. Re-run after changing a prompt or schema:
    .venv\Scripts\python tests\fixtures\record_pipeline.py

Only made-up data is sent: the Jordan Avery fixture resume and the fixture postings.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import anthropic  # noqa: E402

import config  # noqa: E402
from agent import fetch, pipeline  # noqa: E402
from storage import resume  # noqa: E402
from storage.profile import Profile  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "recorded"

CASES = {
    "hockey_with_notes": (
        "jsonld_greenhouse_style.html",
        "Lifelong hockey fan; I play in a weekly adult league in Nashville. "
        "Lead with that, but keep it to a sentence or two.",
    ),
    "plain_company_page": ("plain_company_page.html", ""),
    "prompt_injection": ("prompt_injection.html", ""),
}


class Recorder:
    """Wraps the real client and keeps each step's raw JSON text."""

    def __init__(self, client):
        self.client = client
        self.calls = []
        self.beta = self
        self.messages = self

    def create(self, **kwargs):
        response = self.client.beta.messages.create(**kwargs)
        text = "".join(b.text for b in response.content if b.type == "text")
        self.calls.append({"stop_reason": response.stop_reason, "text": text})
        return response


def main() -> None:
    settings = config.load_settings()
    if settings.key_status != "ok":
        sys.exit("Add your API key to .env first.")
    OUT.mkdir(exist_ok=True)
    resume_text = resume.convert("r.pdf", (HERE / "resume_one_column.pdf").read_bytes())
    profile = Profile(name="Jordan Avery")
    for name, (posting_file, notes) in CASES.items():
        html = (HERE / "postings" / posting_file).read_text(encoding="utf-8")
        posting = fetch.extract(html).text
        rec = Recorder(pipeline.make_client(settings.api_key))
        parsed = pipeline.parse_job(rec, settings.model, posting)
        matches = pipeline.match(rec, settings.model, parsed, resume_text, notes)
        pipeline.draft(rec, settings.model, parsed, matches, resume_text, notes, profile,
                       pipeline.DraftSettings("Professional and warm", "250–400 words"))
        record = {"model": settings.model, "posting_file": posting_file, "notes": notes,
                  "steps": dict(zip(["parse", "match", "draft"], rec.calls))}
        (OUT / f"{name}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Recorded {name}")


if __name__ == "__main__":
    try:
        main()
    except anthropic.APIError as exc:
        sys.exit(f"API error: {exc}")
