"""Job Application Assistant: Streamlit entry point.

Run with:  streamlit run app.py
Each screen lives in ui/; this file runs the start-up checks and the navigation.
"""

import os
import threading

import streamlit as st

import config
from apply import session
from search import schedule
from storage import db
from storage import jobs as job_store
from storage import lock
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


def _open_elsewhere(other: dict) -> None:
    """The app is open on your other computer: wait rather than both changing the data."""
    with st.sidebar:
        style.brand()
    st.title("Open on another computer")
    minutes = int(other["age"] // 60)
    seen = "just now" if minutes < 1 else f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    st.markdown(f"The app is open on **{other.get('host', 'another computer')}** (last seen {seen}). Your "
                "applications sync between your computers, so use the app on one at a time.")
    st.markdown("On that computer, click **Quit app** at the bottom of the sidebar. Give the sync a minute to "
                "finish, then click **Check again**. If that computer is off or its window was just closed, "
                f"this one can start on its own within {lock.STALE // 60} minutes.")
    with st.container(horizontal=True):
        if st.button("Check again", type="primary"):
            st.rerun()
        if st.button("Open anyway", key="lock_override"):
            st.session_state.lock_override = True
            st.rerun()
    st.caption("Open anyway only if the app really isn't running there. If both computers change things at once, "
               "the sync keeps one computer's changes and sets the other's aside.")


def _quit() -> None:
    """Stop the app on this computer and hand the data over to your other computer."""
    current = session.current()
    if current is not None and current.active:
        st.session_state.quit_blocked = True
        return
    lock.release()
    st.session_state.quitting = True
    threading.Timer(1.0, os._exit, (0,)).start()  # after this run sends the goodbye message


def main() -> None:
    if st.session_state.get("quitting"):
        st.title("The app has stopped")
        st.markdown("You can close this tab. To start it again, use the desktop icon.")
        return
    if config.SYNC_FOLDER and not lock.held():
        other = lock.holder()
        if other and not st.session_state.get("lock_override"):
            _open_elsewhere(other)
            return
        lock.acquire()
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
        st.button("Quit app", key="quit_app", on_click=_quit,
                  help="Stops the app on this computer" + (" so your other computer can open it."
                                                           if config.SYNC_FOLDER else "."))
        if st.session_state.pop("quit_blocked", False):
            st.warning("An application is being filled. Close its browser window first.")
    current.run()


if __name__ == "__main__":  # Streamlit runs this file as __main__; tests import its parts
    main()
