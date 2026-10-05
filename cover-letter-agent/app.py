"""Job Application Assistant: Streamlit entry point.

Run with:  streamlit run app.py
Each screen lives in ui/; this file runs the start-up checks and the navigation.
"""

import streamlit as st

import config
from search import schedule
from storage import db
from storage import jobs as job_store
from ui import nav, style
from ui.setup import setup_page

st.set_page_config(page_title="Job Assistant", page_icon="✉️", layout="wide")
style.inject()


@st.cache_resource
def _startup() -> bool:
    """Create data/, output/ and the database, and start the daily-run scheduler, once per
    server process."""
    config.ensure_dirs()
    db.init_db()
    schedule.ensure_started()
    return True


def main() -> None:
    _startup()
    settings = config.load_settings()

    if settings.key_status != "ok":
        with st.sidebar:
            style.brand()
        setup_page(settings)
        return

    current = st.navigation(nav.all_pages(), position="hidden")
    with st.sidebar:
        style.brand()
        new_jobs = job_store.count_jobs()["new"]
        for key, page in nav.sidebar_pages():
            label = f"{page.title} · {new_jobs} new" if key == "find_jobs" and new_jobs else None
            st.page_link(page, label=label)
        style.footnote()
    current.run()


if __name__ == "__main__":  # Streamlit runs this file as __main__; tests import its parts
    main()
