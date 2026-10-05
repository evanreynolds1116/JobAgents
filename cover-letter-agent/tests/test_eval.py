import csv
import importlib.util
import json
from pathlib import Path

import pytest

import config
from agent import pipeline
from storage import resume

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_script", ROOT / "scripts" / "eval.py")
eval_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_script)

LETTER = ("Dear Hiring Manager,\n\n" + "Acme needs someone who ships. " * 45 +
          "\n\nThanks for your time,\nJordan Avery")


@pytest.fixture
def postings(app_paths, monkeypatch, tmp_path):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n")
    resume.save_text("# Jordan Avery\n\nShipped things.")
    folder = tmp_path / "real"
    folder.mkdir()
    (folder / "01.txt").write_text("Backend Engineer at Acme. Must know SQL.", encoding="utf-8")
    (folder / "postings.json").write_text(json.dumps([
        {"id": "01", "expected_company": "Acme", "expected_title": "Backend Engineer", "notes": "",
         "weak_match": True},
        {"id": "02", "expected_company": None, "expected_title": None, "notes": ""},
    ]), encoding="utf-8")

    parsed = {"company": "Acme Corp", "title": "Backend Engineer", "location": None, "must_have": ["SQL"],
              "nice_to_have": [], "responsibilities": [], "keywords": [], "contact_name": None,
              "tone_signals": None, "several_jobs": False}
    matches = {"matches": [{"requirement": "SQL", "kind": "must_have", "evidence": [], "strength": "none",
                            "feature": False}]}
    verify = {"claims": [{"claim": "who ships", "supported": True, "source": "resume", "evidence": "Shipped",
                          "reason": ""}], "style_flags": [], "lint": []}
    monkeypatch.setattr(pipeline, "make_client", lambda key: object())
    monkeypatch.setattr(pipeline, "parse_job", lambda *a: parsed)
    monkeypatch.setattr(pipeline, "match", lambda *a: matches)
    monkeypatch.setattr(pipeline, "draft", lambda *a: LETTER)
    monkeypatch.setattr(pipeline, "humanize", lambda *a: (LETTER, []))
    flagged = {"claims": [{"claim": "who ships", "supported": False, "source": "none", "evidence": "",
                           "reason": "Not in your resume."}], "style_flags": [], "lint": []}
    checks = iter([flagged, verify])  # flagged first, clean after the fix-up
    monkeypatch.setattr(pipeline, "verify", lambda *a: next(checks))
    monkeypatch.setattr(pipeline, "fix_claims", lambda *a: (LETTER, ["Reworded one claim"]))
    return folder


def test_eval_writes_report_and_scoresheet(postings, tmp_path):
    report = eval_script.main(["--yes"], folder=postings, out_root=tmp_path / "out")
    out = report.parent
    text = report.read_text(encoding="utf-8")
    assert "Correct company and title: 1 of 1" in text
    assert "Letters with zero unsupported claims: 1 of 1 (before the automatic fix-up: 0)" in text
    assert "| Unsupported claims | 0 (fix-up changes: 1) |" in text
    assert "Skipped (no posting text saved yet): 02" in text
    assert "Weak match on purpose" in text
    assert "| who ships | yes | resume |  |" in text
    assert (out / "01.md").read_text(encoding="utf-8") == LETTER
    saved = json.loads((out / "01.json").read_text(encoding="utf-8"))
    assert saved["score"]["must_haves_with_evidence"] == "0 of 1"
    assert set(saved["seconds"]) == {"parse", "match", "draft", "humanize", "trim", "verify", "fix", "trim_again",
                                     "verify_again"}
    assert saved["trims"] == [] and "| Length within target | **no** (trim cuts: 0) |" in text
    rows = list(csv.reader(open(out / "scores.csv", encoding="utf-8")))
    assert rows[0][-1] == "comments" and "You'd send it after light edits" in rows[0]
    assert rows[1][:4] == ["01", "Acme Corp", "Backend Engineer", "True"]


def test_eval_asks_before_spending(postings, tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert eval_script.main([], folder=postings, out_root=tmp_path / "out") is None
    assert not (tmp_path / "out").exists()


def test_score_checks():
    item = {"expected_company": "Acme", "expected_title": "Engineer", "notes": "I love SQL"}
    parsed = {"company": "Acme Corp", "title": "Senior Engineer"}
    matches = {"matches": [{"kind": "must_have", "strength": s} for s in ("strong", "partial", "none", "strong")]}
    checked = {"claims": [{"supported": True, "source": "notes"}], "style_flags": [], "lint": []}
    s = eval_script.score(item, parsed, matches, "Acme " + "word " * 300 + "leverage", checked, "250–400 words")
    assert s["company_title_correct"] and s["must_haves_ok"] and s["must_haves_with_evidence"] == "3 of 4"
    assert s["banned_phrases"] == 1 and s["length_ok"] and s["company_named"] and s["notes_used"] is True


@pytest.mark.parametrize("company, letter, named", [
    ("Regal Cinemas", "I'd like to help Regal's guests.", True),
    ("Acme Corp", "Acme needs this.", True),
    ("Tilt", "Tilt is hiring.", True),
    ("Axios", "Your company is great.", False),
    ("OnePay", "I'd join OnePayments.", False),
])
def test_names_company(company, letter, named):
    assert eval_script.names_company(company, letter) is named
