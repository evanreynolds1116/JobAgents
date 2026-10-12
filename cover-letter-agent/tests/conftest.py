import pytest
import streamlit as st

import config


@pytest.fixture
def app_paths(tmp_path, monkeypatch):
    """Point .env, data/ and output/ at a temp folder so tests never touch real data."""
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "app.db")
    monkeypatch.setattr(config, "LOCAL_DIR", tmp_path / "local")
    monkeypatch.setattr(config, "SYNC_FOLDER", None)
    st.cache_resource.clear()
    return tmp_path
