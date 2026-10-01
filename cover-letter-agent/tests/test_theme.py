import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_streamlit_config():
    with open(ROOT / ".streamlit" / "config.toml", "rb") as f:
        return tomllib.load(f)


def test_bundled_fonts_exist_and_nothing_loads_remotely():
    cfg = load_streamlit_config()
    assert cfg["server"]["enableStaticServing"] is True
    faces = cfg["theme"]["fontFaces"]
    assert {f["family"] for f in faces} == {"Public Sans", "IBM Plex Mono", "Source Serif 4"}
    for face in faces:
        assert face["url"].startswith("app/static/"), face["url"]
        assert (ROOT / face["url"].removeprefix("app/")).is_file(), face["url"]
    assert "http" not in cfg["theme"]["font"] + cfg["theme"]["codeFont"]


def test_usage_stats_off():
    assert load_streamlit_config()["browser"]["gatherUsageStats"] is False
