"""Applications list: every application with its status, letter and next step."""

from html import escape

import streamlit as st

from agent import pipeline
from storage import db
from ui import dates, nav
from ui.style import muted

FILTERS = {
    "All": lambda a: True,
    "In progress": lambda a: a["status"] in ("draft", "approved"),
    "Submitted": lambda a: a["status"] == "submitted",
    "Archived": lambda a: a["status"] == "archived",
}


def status_label(app: dict) -> str:
    return {
        "draft": "Draft",
        "approved": "Letter approved",
        "submitted": f"Submitted {dates.day(app.get('submitted_at'))}".strip(),
        "archived": "Archived",
    }[app["status"]]


def letter_label(app: dict) -> str:
    if not app.get("latest_version"):
        return "No letter"
    if app.get("sent_version"):
        return f"Approved v{app['sent_version']}"
    label = f"Draft v{app['latest_version']}"
    if app.get("latest_verify") is None:
        return label + " · not checked"
    flags = pipeline.flag_count(app["latest_verify"])
    return label + (f" · {flags} flag{'s' if flags != 1 else ''}" if flags else "")


def next_step(app: dict) -> tuple[str, str]:
    """(button label, action) for the row."""
    if app["status"] == "archived":
        return "Restore", "restore"
    if app["status"] == "submitted":
        return "Open details", "detail"
    if app["status"] == "approved":
        return "Open letter", "review"
    return ("Review draft", "review") if app.get("latest_version") else ("Open details", "detail")


def applications_page() -> None:
    st.title("Applications")
    everything = db.list_applications()
    submitted = sum(1 for a in everything if a["status"] == "submitted")
    muted(f"{len(everything)} application{'s' if len(everything) != 1 else ''} · {submitted} submitted")

    if not everything:
        with st.container(border=True, key="card_no_apps"):
            st.markdown("**No applications yet.** Each cover letter you start is saved here.")
            if st.button("New cover letter", type="primary"):
                nav.go("new_letter")
        return

    search = st.text_input("Search applications", key="ap_search",
                           placeholder="Search by company or title", label_visibility="collapsed")
    found = db.list_applications(search) if search.strip() else everything
    counts = {name: sum(1 for a in found if test(a)) for name, test in FILTERS.items()}
    choice = st.segmented_control("Show", list(FILTERS), default="All", key="ap_filter",
                                  format_func=lambda n: f"{n} ({counts[n]})", label_visibility="collapsed")
    rows = [a for a in found if FILTERS[choice or "All"](a)]

    with st.container(border=True, key="card_app_list"):
        widths = [3, 1.8, 1.8, 1.5, 1.9]
        header = st.columns(widths)
        for col, label in zip(header, ["Role", "Status", "Cover letter", "Last activity", ""]):
            col.caption(label)
        if not rows:
            st.caption("No applications match.")
        for app in rows:
            role, status, letter, when, action = st.columns(widths, vertical_alignment="center")
            if role.button(app.get("title") or "Untitled job", key=f"ap_open_{app['id']}", type="tertiary"):
                nav.go("detail", app=app["id"])
            role.markdown(f'<span class="ja-muted">{escape(app.get("company") or "Unknown company")}</span>',
                          unsafe_allow_html=True)
            status.markdown(status_label(app))
            letter.markdown(letter_label(app))
            when.markdown(dates.friendly(app["last_activity"]))
            label, kind = next_step(app)
            if action.button(label, key=f"ap_action_{app['id']}", width="stretch"):
                if kind == "restore":
                    db.restore(app["id"])
                    st.rerun()
                nav.go(kind, app=app["id"])
