"""Milestone 11 acceptance sheet: export postings to label, then score the labels."""

import csv
import importlib.util
from datetime import datetime
from pathlib import Path

from search.normalize import Job
from storage import db
from storage import jobs as store

spec = importlib.util.spec_from_file_location("label_jobs", Path(__file__).resolve().parents[1] / "scripts" / "label_jobs.py")
label_jobs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(label_jobs)


def add(n: int, setting: str, fit: int | None):
    job = Job("adzuna", str(n), f"Engineer {n}", f"Company {n}", "Nashville, Davidson County", setting, None, None,
              False, f"2026-10-0{1 + n % 5}T09:00:00", f"https://example.com/{n}", "Snippet", fit=fit,
              fit_reason=f"Reason {n}" if fit else "")
    store.upsert(job, None, datetime.now().isoformat(timespec="seconds"))


def test_export_mixes_settings_and_skips_unscored(app_paths):
    db.init_db()
    for n in range(30):
        add(n, ["remote", "remote", "remote", "hybrid", "unknown", "onsite"][n % 6], fit=None if n == 0 else 1 + n % 5)
    path = label_jobs.main([], out_root=app_paths / "out")
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    assert len(rows) == 20 and "0" not in [r["id"] for r in rows]
    settings = [r["claude_setting"] for r in rows]
    assert {s: settings.count(s) for s in set(settings)} == {"remote": 5, "hybrid": 5, "onsite": 5, "unknown": 5}
    assert list(rows[0]) == label_jobs.COLUMNS and rows[0]["your_setting"] == ""


def test_check_scores_settings_and_picks(tmp_path):
    path = tmp_path / "labels.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(label_jobs.COLUMNS)
        for n in range(20):
            claude = "remote" if n < 18 else "unknown"
            yours = "Remote" if n != 19 else "hybrid"  # 18 right: row 18 wrong (unknown vs remote) and 19
            writer.writerow([n, f"Engineer {n}", "Acme", "Nashville", "", "", claude, 5 - n // 4, f"R{n}", yours,
                             "x" if n in (0, 1, 2, 3, 10) else ""])
    report = label_jobs.main(["--check", str(path)])
    assert "Right: 18 of 20 labeled (target: 17 of 20) (meets the target)" in report
    assert "| Engineer 19 at Acme | unknown | hybrid |" in report
    assert "Your picks Claude scored 4 or 5: 4 of 5" in report
    assert "Claude's top 5 include 4 of your picks" in report
    assert (tmp_path / "report.md").exists()
