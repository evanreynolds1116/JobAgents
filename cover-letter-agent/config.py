"""Settings loaded from .env, plus the app's folder locations.

API keys are never logged or shown; only their status is exposed to the UI.
"""

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
DB_PATH = DATA_DIR / "app.db"

DEFAULT_MODEL = "claude-opus-5-5"
KEY_PREFIX = "sk-ant-"


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str
    adzuna_app_id: str | None = field(default=None, repr=False)
    adzuna_app_key: str | None = field(default=None, repr=False)

    @property
    def adzuna_status(self) -> str:
        """'missing' unless both Adzuna values are set (needed for job search only)."""
        return "ok" if self.adzuna_app_id and self.adzuna_app_key else "missing"

    @property
    def key_status(self) -> str:
        """'missing', 'invalid' (wrong format) or 'ok'. Checked locally, no API call."""
        if not self.api_key:
            return "missing"
        if not self.api_key.startswith(KEY_PREFIX) or len(self.api_key) < 20:
            return "invalid"
        return "ok"

    def __repr__(self) -> str:  # keep the key out of logs and tracebacks
        return f"Settings(api_key=<{self.key_status}>, model={self.model!r}, adzuna=<{self.adzuna_status}>)"


def load_settings(env_path: Path | None = None) -> Settings:
    """Read .env fresh on every call, so editing it takes effect without a restart."""
    env_path = env_path or ENV_PATH
    values = dotenv_values(env_path) if env_path.exists() else {}
    api_key = (values.get("ANTHROPIC_API_KEY") or "").strip() or None
    model = (values.get("ANTHROPIC_MODEL") or "").strip() or DEFAULT_MODEL
    return Settings(
        api_key=api_key,
        model=model,
        adzuna_app_id=(values.get("ADZUNA_APP_ID") or "").strip() or None,
        adzuna_app_key=(values.get("ADZUNA_APP_KEY") or "").strip() or None,
    )


def ensure_dirs() -> None:
    for folder in (DATA_DIR, OUTPUT_DIR):
        folder.mkdir(parents=True, exist_ok=True)
