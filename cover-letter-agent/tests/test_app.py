from pathlib import Path

from streamlit.testing.v1 import AppTest

import config

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def run_app():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def test_missing_key_shows_setup_instructions(app_paths):
    at = run_app()
    assert at.title[0].value == "Connect your Claude API key"
    assert "No Claude API key" in at.warning[0].value
    assert any(".env.example" in md.value for md in at.markdown)


def test_invalid_key_shows_setup_instructions(app_paths):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=not-a-real-key\n")
    at = run_app()
    assert at.title[0].value == "Connect your Claude API key"
    assert len(at.error) == 1


def test_check_again_picks_up_new_key(app_paths):
    at = run_app()
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n")
    at.button[0].click().run()
    assert at.title[0].value == "New cover letter"


def test_starts_with_key_and_creates_database(app_paths):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n")
    at = run_app()
    assert at.title[0].value == "New cover letter"
    assert config.DB_PATH.exists()
    assert config.OUTPUT_DIR.is_dir()
