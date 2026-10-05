"""Application detail: everything you need when a recruiter calls.

Key dates, the saved job description (kept even after the posting comes down),
the exact letter version you approved, and a dated notes log.
"""

from html import escape

import streamlit as st

from storage import db, filled
from ui import dates, nav
from ui.applications import status_label


def _app_id() -> int | None:
    try:
        return int(st.query_params.get("app"))
    except (TypeError, ValueError):
        return None


def _md(text: str) -> str:
    return text.replace("$", r"\$")


def detail_page() -> None:
    app_id = _app_id()
    app = db.get_application(app_id) if app_id else None
    if not app:
        st.title("Application details")
        st.info("No application is open. Pick one from Applications.")
        if st.button("Applications", type="primary"):
            nav.go("applications")
        return
    drafts = db.list_drafts(app_id)
    company = app.get("company") or "Unknown company"
    parsed = app.get("parsed_json") or {}

    st.markdown(f'<p class="ja-crumb">Applications › {escape(company)}</p>', unsafe_allow_html=True)
    st.title(app.get("title") or "Untitled job")
    facts = [company] + ([parsed["location"]] if parsed.get("location") else [])
    line = " · ".join(escape(f) for f in facts)
    if app.get("url"):
        line += f' · <a href="{escape(app["url"])}" target="_blank">Original posting link</a>'
    chip = {"submitted": "ja-strong", "approved": "ja-strong", "draft": "ja-partial", "archived": "ja-none"}[app["status"]]
    st.markdown(f'<span class="ja-strength {chip}">{escape(status_label(app))}</span> '
                f'<span class="ja-muted" style="margin-left:8px">{line}</span>', unsafe_allow_html=True)

    if flash := st.session_state.pop("dt_flash", None):
        st.success(flash)
    _key_dates(app)
    _actions(app, drafts)

    left, right = st.columns([3, 2], gap="large")
    with left:
        _tabs(app, drafts)
    with right:
        _notes(app)


def _key_dates(app: dict) -> None:
    notes = app.get("notes") or []
    last_note = notes[-1] if notes else None
    cards = [
        ("Found", dates.day(app["created_at"]), "Saved to the app"),
        ("Letter approved", dates.day(app.get("approved_at")) or "Not yet",
         f"Version {app['sent_version']}" if app.get("sent_version") else ""),
        ("Applied", dates.day(app.get("submitted_at")) or "Not yet",
         "You submitted" if app.get("submitted_at") else ""),
        ("Last update", dates.day(last_note["date"]) if last_note else dates.day(db.last_activity(app)),
         (last_note["text"][:40] + ("…" if len(last_note["text"]) > 40 else "")) if last_note else ""),
    ]
    for col, (label, value, sub) in zip(st.columns(4), cards):
        with col, st.container(border=True, key=f"card_date_{label.replace(' ', '_').lower()}"):
            st.caption(label)
            st.markdown(f"**{escape(value)}**")
            if sub:
                st.caption(sub)


def _actions(app: dict, drafts: list[dict]) -> None:
    app_id = app["id"]
    with st.container(horizontal=True):
        if drafts and st.button("Open letter", type="primary"):
            nav.go("review", app=app_id)
        if app.get("url") and app["status"] in ("draft", "approved") and st.button(
                "Fill application" if app["status"] == "approved" else "Fill without cover letter"):
            nav.go("apply", app=app_id)
        if app["status"] in ("draft", "approved") and st.button("Mark as submitted"):
            db.mark_submitted(app_id)
            st.session_state.dt_flash = "Marked as submitted today. Good luck!"
            st.rerun()
        if app["status"] == "archived":
            if st.button("Restore"):
                db.restore(app_id)
                st.rerun()
        elif st.button("Archive"):
            db.archive(app_id)
            st.rerun()
    if app["status"] in ("draft", "approved"):
        st.caption("The app never submits anything. After you apply on the company's site, mark it here "
                   "to record the date.")


def _tabs(app: dict, drafts: list[dict]) -> None:
    sent = next((d for d in drafts if d["version"] == app.get("sent_version")), None)
    letter_tab = f"Cover letter sent (v{sent['version']})" if sent else "Cover letter"
    description, letter, answers = st.tabs(["Job description", letter_tab, "Your answers"])
    with description, st.container(border=True, key="card_posting"):
        st.caption(f"Saved copy from {dates.day(app['created_at'])}. It stays here even if the original "
                   "posting is taken down.")
        st.markdown(_md(app.get("posting_text") or ""))
    with letter, st.container(border=True, key="card_sent_letter"):
        if sent:
            st.caption(f"Approved {dates.full(app['approved_at'])}" if app.get("approved_at")
                       else f"Version {sent['version']}")
            from ui.review import letter_html
            st.markdown(letter_html(sent["text"], None), unsafe_allow_html=True)
        elif drafts:
            st.markdown(f"No approved letter yet. The latest draft is version {drafts[0]['version']}.")
        else:
            st.markdown("No letter for this application.")
    with answers, st.container(border=True, key="card_answers"):
        rows = filled.for_application(app["id"])
        if not rows:
            st.markdown("**No form answers yet.**")
            st.caption("When the application agent fills this job's form, every field's final value, including "
                       "your edits, is recorded here.")
        else:
            from ui.apply import SOURCE, STATUS
            st.caption(f"Recorded {dates.full(rows[-1]['filled_at'])}, including your edits in the browser.")
            st.dataframe([{"Page": r["page"], "Field": r["field_label"], "Value": r["value"] or "",
                           "Source": SOURCE.get(r["source"], r["source"] or ""),
                           "Status": STATUS.get(r["status"], r["status"] or "")} for r in rows],
                         hide_index=True, width="stretch")


def _notes(app: dict) -> None:
    with st.container(border=True, key="card_notes_log"):
        st.subheader("Notes", anchor=False)
        st.text_area("Add a note", key=f"dt_note_{app['id']}", height=100,
                     placeholder="Recruiter call, interview times, who you spoke with…")
        st.button("Save note", on_click=_save_note, args=(app["id"],))
        for note in reversed(app.get("notes") or []):
            st.caption(dates.full(note["date"]))
            st.markdown(_md(escape(note["text"])).replace("\n", "  \n"))


def _save_note(app_id: int) -> None:
    key = f"dt_note_{app_id}"
    text = (st.session_state.get(key) or "").strip()
    if text:
        db.add_note(app_id, text)
        st.session_state[key] = ""
