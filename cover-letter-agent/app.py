"""Job Application Assistant: Streamlit entry point.

Run with:  streamlit run app.py
Each screen lives in ui/; this file runs the start-up checks and the navigation.
"""

import streamlit as st

import config
from storage import db
from ui import nav, style
from ui.setup import setup_page

st.set_page_config(page_title="Job Assistant", page_icon="✉️", layout="wide")
style.inject()


@st.cache_resource
def _startup() -> bool:
    """Create data/, output/ and the database once per server process."""
    config.ensure_dirs()
    db.init_db()
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
        for page in nav.sidebar_pages():
            st.page_link(page)
        style.footnote()
    current.run()


if __name__ == "__main__":  # Streamlit runs this file as __main__; tests import its parts
    main()
