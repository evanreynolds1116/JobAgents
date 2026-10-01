r"""Quality evaluation (spec: Testing & evaluation): run the saved postings through all
five steps and save each letter next to its verifier report for you to score.

    .venv\Scripts\python scripts\eval.py            # asks before spending money
    .venv\Scripts\python scripts\eval.py --yes      # no prompt
    .venv\Scripts\python scripts\eval.py --only 01,04

Postings live in tests/fixtures/real/ (gitignored): NN.txt holds the posting text and
postings.json lists each one's expected company and title, optional job notes and
whether your resume is a weak match. Results go to output/eval/<date-time>/ (gitignored).
"""

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from agent import lint, pipeline  # noqa: E402
from storage import profile as profile_store  # noqa: E402
from storage import resume  # noqa: E402

POSTINGS = ROOT / "tests" / "fixtures" / "real"
COST_PER_POSTING = 0.08  # rough, in US dollars, for five Opus calls

MANUAL = [
    "Uses your job notes naturally (if any)",
    "Varied sentences; sounds like you",
    "Reads as specific to this company",
    "You'd send it after light edits",
]


def load_manifest(folder: Path) -> list[dict]:
    manifest = json.loads((folder / "postings.json").read_text(encoding="utf-8"))
    for item in manifest:
        item["text_path"] = folder / f"{item['id']}.txt"
    return manifest


def _same(found: str | None, expected: str | None) -> bool:
    if not expected:
        return True
    a, b = (found or "").lower(), expected.lower()
    return bool(a) and (a in b or b in a)


def names_company(company: str | None, letter: str) -> bool:
    """'Acme Corp' counts as named if the letter says 'Acme'."""
    if not company:
        return False
    short = re.sub(r"[,.]?\s+(inc|corp|corporation|co|company|llc|ltd|group)\.?$", "", company.strip(), flags=re.I)
    return any(name.lower() in letter.lower() for name in (company, short))


def score(item: dict, parsed: dict, matches: dict, letter: str, checked: dict, length: str) -> dict:
    """The checks code can make. The rest are yours (see MANUAL)."""
    words = pipeline.word_count(letter)
    low, high = (150, 250) if length.startswith("Short") else (250, 400)
    must = [m for m in matches["matches"] if m["kind"] == "must_have"]
    addressed = [m for m in must if m["strength"] != "none"]
    flags = pipeline.flags(checked)
    notes_used = any(c["source"] == "notes" and c["supported"] for c in checked["claims"])
    return {
        "company_title_correct": _same(parsed["company"], item.get("expected_company"))
        and _same(parsed["title"], item.get("expected_title")),
        "must_haves_with_evidence": f"{len(addressed)} of {len(must)}",
        "must_haves_ok": len(addressed) >= min(3, len(must)),
        "unsupported_claims": len(flags["claims"]),
        "banned_phrases": sum(1 for h in lint.lint(letter) if h.kind == "phrase"),
        "style_flags": len(flags["style"]) + len(flags["lint"]),
        "words": words,
        "length_ok": low <= words <= high,
        "company_named": names_company(parsed["company"], letter),
        "notes_used": notes_used if item.get("notes") else None,
    }


def run_one(client, model: str, item: dict, resume_text: str, profile, settings) -> dict:
    posting = item["text_path"].read_text(encoding="utf-8")
    notes = item.get("notes") or ""
    times = {}

    def timed(step, fn, *args):
        start = time.time()
        result = fn(*args)
        times[step] = round(time.time() - start, 1)
        return result

    parsed = timed("parse", pipeline.parse_job, client, model, posting)
    matches = timed("match", pipeline.match, client, model, parsed, resume_text, notes)
    draft = timed("draft", pipeline.draft, client, model, parsed, matches, resume_text, notes, profile, settings)
    letter, changes = timed("humanize", pipeline.humanize, client, model, draft, profile, settings)
    checked = timed("verify", pipeline.verify, client, model, letter, resume_text, profile, notes, posting)
    return {"id": item["id"], "parsed": parsed, "matches": matches, "first_draft": draft, "letter": letter,
            "humanize_changes": changes, "verify": checked, "seconds": times,
            "score": score(item, parsed, matches, letter, checked, settings.length)}


def _yes(value) -> str:
    return {True: "yes", False: "**no**", None: "n/a"}.get(value, str(value))


def write_report(out: Path, item_results: list[dict], manifest: dict, skipped: list[str]) -> Path:
    lines = [f"# Cover letter evaluation, {datetime.now():%B %d, %Y %H:%M}", ""]
    done = [r for r in item_results if "error" not in r]
    correct = sum(r["score"]["company_title_correct"] for r in done)
    lines += [
        "## Summary", "",
        f"- Postings run: {len(done)} (failed: {len(item_results) - len(done)}, skipped: {len(skipped)})",
        f"- Correct company and title: {correct} of {len(done)} (target: 9 of 10)",
        f"- Letters with zero unsupported claims: {sum(r['score']['unsupported_claims'] == 0 for r in done)} of {len(done)}",
        f"- Letters with no banned phrases: {sum(r['score']['banned_phrases'] == 0 for r in done)} of {len(done)}",
        f"- Length within target: {sum(r['score']['length_ok'] for r in done)} of {len(done)}",
        f"- Average time per letter: {sum(sum(r['seconds'].values()) for r in done) / max(len(done), 1):.0f} seconds",
        "", "Score the judgment calls in `scores.csv`: " + "; ".join(MANUAL) + ".", "",
    ]
    if skipped:
        lines += ["Skipped (no posting text saved yet): " + ", ".join(skipped), ""]
    for r in item_results:
        item = manifest[r["id"]]
        lines += ["---", "", f"## {r['id']}. {item.get('expected_title') or ''} at {item.get('expected_company') or ''}", ""]
        if item.get("weak_match"):
            lines += ["*Weak match on purpose: check that nothing is invented to close the gap.*", ""]
        if "error" in r:
            lines += [f"**Failed:** {r['error']}", ""]
            continue
        s = r["score"]
        lines += [
            f"Parsed as **{r['parsed']['title']}** at **{r['parsed']['company']}** "
            f"({'correct' if s['company_title_correct'] else '**check this**'}). "
            f"{s['words']} words, {sum(r['seconds'].values()):.0f} seconds.", "",
            "| Check | Result |", "|---|---|",
            f"| Must-haves with evidence | {s['must_haves_with_evidence']} ({_yes(s['must_haves_ok'])}) |",
            f"| Unsupported claims | {s['unsupported_claims']} |",
            f"| Banned phrases | {s['banned_phrases']} |",
            f"| Other style flags | {s['style_flags']} |",
            f"| Length within target | {_yes(s['length_ok'])} |",
            f"| Names the company | {_yes(s['company_named'])} |",
            f"| Job notes used | {_yes(s['notes_used'])} |", "",
            "### Letter", "", r["letter"], "",
            "### Verifier report", "",
            "| Claim | Supported | Source | Why |", "|---|---|---|---|",
        ]
        for c in r["verify"]["claims"]:
            claim = c["claim"].replace("|", "\\|").replace("\n", " ")
            why = (c["reason"] or "").replace("|", "\\|")
            lines.append(f"| {claim} | {'yes' if c['supported'] else '**no**'} | {c['source']} | {why} |")
        for f in r["verify"]["style_flags"]:
            lines.append(f"| *Style:* {f['text']} | | | {f['issue']} |")
        lines.append("")
    path = out / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")

    with open(out / "scores.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "company", "title", "company_title_correct", "unsupported_claims",
                         "banned_phrases", "words", "length_ok"] + MANUAL + ["comments"])
        for r in done:
            s = r["score"]
            writer.writerow([r["id"], r["parsed"]["company"], r["parsed"]["title"], s["company_title_correct"],
                             s["unsupported_claims"], s["banned_phrases"], s["words"], s["length_ok"]]
                            + [""] * len(MANUAL) + [""])
    return path


def main(argv: list[str] | None = None, folder: Path = POSTINGS, out_root: Path | None = None) -> Path | None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated posting ids, e.g. 01,04")
    parser.add_argument("--yes", action="store_true", help="don't ask before calling the API")
    args = parser.parse_args(argv)

    settings = config.load_settings()
    if settings.key_status != "ok":
        sys.exit("Add your Claude API key to .env first.")
    if not resume.has_resume():
        sys.exit("Add your resume on the Profile & resume screen first.")
    manifest = load_manifest(folder)
    if args.only:
        wanted = set(args.only.split(","))
        manifest = [m for m in manifest if m["id"] in wanted]
    ready = [m for m in manifest if m["text_path"].exists()]
    skipped = [m["id"] for m in manifest if not m["text_path"].exists()]
    if not ready:
        sys.exit("No posting text found. Save postings as tests/fixtures/real/NN.txt.")

    estimate = len(ready) * COST_PER_POSTING
    print(f"{len(ready)} postings, five API calls each, roughly ${estimate:.2f} with {settings.model}.")
    if skipped:
        print("Skipping (no text yet): " + ", ".join(skipped))
    if not args.yes and input("Continue? [y/N] ").strip().lower() != "y":
        return None

    out = (out_root or config.OUTPUT_DIR / "eval") / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    client = pipeline.make_client(settings.api_key)
    resume_text = resume.load_text()
    profile = profile_store.load()
    draft_settings = pipeline.DraftSettings(profile.tone, profile.length)
    results = []
    for item in ready:
        print(f"{item['id']}: ", end="", flush=True)
        try:
            result = run_one(client, settings.model, item, resume_text, profile, draft_settings)
        except pipeline.PipelineError as exc:
            result = {"id": item["id"], "error": exc.message}
            print(f"failed ({exc.message})", flush=True)
        else:
            s = result["score"]
            print(f"{result['parsed']['company']} / {result['parsed']['title']}, {s['words']} words, "
                  f"{s['unsupported_claims']} unsupported, {sum(result['seconds'].values()):.0f} s", flush=True)
            (out / f"{item['id']}.md").write_text(result["letter"], encoding="utf-8")
        (out / f"{item['id']}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(result)
    report = write_report(out, results, {m["id"]: m for m in manifest}, skipped)
    print(f"Report: {report}")
    return report


if __name__ == "__main__":
    main()
