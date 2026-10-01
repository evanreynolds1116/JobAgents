import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.parametrize("path", [".env", "data/app.db", "data/resume.md", "output/letter.docx"])
def test_private_paths_are_gitignored(tmp_path, path):
    shutil.copy(ROOT / ".gitignore", tmp_path / ".gitignore")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=tmp_path)
    assert result.returncode == 0, f"{path} is not gitignored"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.parametrize("path", ["app.py", ".env.example", "agent/style/banned_phrases.txt"])
def test_project_files_are_not_ignored(tmp_path, path):
    shutil.copy(ROOT / ".gitignore", tmp_path / ".gitignore")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=tmp_path)
    assert result.returncode == 1, f"{path} should not be ignored"
