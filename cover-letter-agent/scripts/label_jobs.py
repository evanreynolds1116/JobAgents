r"""Milestone 11 acceptance check: compare Claude's work settings and fit scores with yours.

    .venv\Scripts\python scripts\label_jobs.py                  # write a sheet of 20 postings to label
    .venv\Scripts\python scripts\label_jobs.py --check FILE     # score your filled-in sheet

The sheet goes to output/job_labels/<date-time>/labels.csv (gitignored). For each row, open
the link and fill in `your_setting` (remote, hybrid, onsite, or unknown if the full posting
doesn't say), and put an x in `your_pick` for your top 5. Claude's answers are in the sheet
too; label from the posting, not from them. Costs nothing: it reads jobs already in the app.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from storage.db import connect  # noqa: E402

SIZE = 20
SETTINGS = ("remote", "hybrid", "onsite", "unknown")
COLUMNS = ["id", "title", "company", "location", "link", "snippet", "claude_setting", "claude_fit",
           "claude_reason", "your_setting", "your_pick"]
TARGET = 17  # of 20 with the right work setting (spec)


def pick_jobs(size: int = SIZE) -> list[dict]:
    """Scored jobs, newest first, taken in turn from each of Claude's settings so the sheet
    has a mix rather than mostly one kind."""
    with connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM jobs WHERE fit IS NOT NULL ORDER BY COALESCE(posted_at, first_seen_at) DESC, id DESC")]
    conn.close()
    groups = {s: [r for r in rows if r["work_setting"] == s] for s in SETTINGS}
    chosen = []
    while len(chosen) < size and any(groups.values()):
        for s in SETTINGS:
            if groups[s] and len(chosen) < size:
                chosen.append(groups[s].pop(0))
    return chosen


def export(out_root: Path) -> Path:
    jobs = pick_jobs()
    if not jobs:
        sys.exit("No scored jobs yet. Run a search on Find jobs first.")
    out = out_root / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "labels.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel reads UTF-8
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for j in jobs:
            writer.writerow([j["id"], j["title"], j["company"], j["location"], j["apply_url"], j["description"],
                             j["work_setting"], j["fit"], j["fit_reason"], "", ""])
    note = "" if len(jobs) == SIZE else f" (only {len(jobs)} scored jobs so far; the target needs {SIZE})"
    print(f"Wrote {len(jobs)} postings to {path}{note}")
    return path


def check(path: Path) -> str:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    labeled = [r for r in rows if r["your_setting"].strip()]
    bad = [r for r in labeled if r["your_setting"].strip().lower() not in SETTINGS]
    if bad:
        sys.exit(f"your_setting must be one of {', '.join(SETTINGS)}; check rows {', '.join(r['id'] for r in bad)}.")
    right = [r for r in labeled if r["your_setting"].strip().lower() == r["claude_setting"]]
    wrong = [r for r in labeled if r not in right]

    picks = [r for r in rows if r["your_pick"].strip()]
    ranked = sorted(rows, key=lambda r: -int(r["claude_fit"]))  # stable: ties keep the sheet's order
    top = ranked[:len(picks)]
    high = [r for r in picks if int(r["claude_fit"]) >= 4]
    others = [r for r in rows if r not in picks]

    def avg(group):
        return sum(int(r["claude_fit"]) for r in group) / len(group) if group else 0

    lines = [f"# Work setting and fit check, {datetime.now():%B %d, %Y %H:%M}", "",
             "## Work setting", "",
             f"- Right: {len(right)} of {len(labeled)} labeled (target: {TARGET} of {SIZE}) "
             f"({'meets' if len(right) >= TARGET and len(labeled) >= SIZE else 'does not meet'} the target)"]
    if wrong:
        lines += ["", "| Job | Claude | You |", "|---|---|---|"]
        lines += [f"| {r['title']} at {r['company']} | {r['claude_setting']} | {r['your_setting'].strip().lower()} |"
                  for r in wrong]
    lines += ["", "## Your top picks", ""]
    if picks:
        lines += [f"- Your picks Claude scored 4 or 5: {len(high)} of {len(picks)}",
                  f"- Claude's top {len(picks)} include {len([r for r in top if r in picks])} of your picks",
                  f"- Average fit: your picks {avg(picks):.1f}, the rest {avg(others):.1f}", "",
                  "| Your pick | Claude's fit | Claude's reason |", "|---|---|---|"]
        lines += [f"| {r['title']} at {r['company']} | {r['claude_fit']} | {r['claude_reason']} |" for r in picks]
    else:
        lines.append("- No picks marked yet: put an x in `your_pick` for your top 5.")
    report = "\n".join(lines) + "\n"
    (path.parent / "report.md").write_text(report, encoding="utf-8")
    return report


def main(argv: list[str] | None = None, out_root: Path | None = None) -> str | Path:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", type=Path, help="a labels.csv you've filled in")
    args = parser.parse_args(argv)
    if args.check:
        report = check(args.check)
        print(report)
        return report
    return export(out_root or config.OUTPUT_DIR / "job_labels")


if __name__ == "__main__":
    main()
