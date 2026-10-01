"""Review screen for a drafted letter.

Milestone 3 shows the posting summary, the requirement match, the draft and its
versions. Milestone 4 adds claim checks, inline editing, revise-with-feedback and Approve.
"""

from datetime import datetime
from html import escape

import streamlit as st

from agent import pipeline
from storage import db
from ui import nav

STRENGTH_LABEL = {"strong": "Strong", "partial": "Partial", "none": "None"}


def _app_id() -> int | None:
    raw = st.query_params.get("app")
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def _md(text: str) -> str:
    """Show letter text as written: keep single line breaks (sign-off, name) and stop
    $ signs turning into math formatting."""
    return text.replace("$", r"\$").replace("\n", "  \n")


def review_page() -> None:
    app_id = _app_id()
    app = db.get_application(app_id) if app_id else None
    if not app:
        st.title("Review and approve")
        st.info("No letter is open. Start one on the New cover letter screen.")
        if st.button("New cover letter", type="primary"):
            nav.go("new_letter")
        return

    drafts = db.list_drafts(app_id)
    parsed = app.get("parsed_json") or {}
    company = app.get("company") or "Unknown company"
    title = app.get("title") or "Untitled job"

    st.markdown(f'<p class="ja-crumb">Applications › {escape(company)}</p>', unsafe_allow_html=True)
    st.title(title)
    if drafts:
        st.caption(f"{app['status'].capitalize()} · version {drafts[0]['version']}")
    facts = [company] + [parsed.get(k) for k in ("location",) if parsed.get(k)]
    line = " · ".join(escape(f) for f in facts)
    if app.get("url"):
        line += f' · <a href="{escape(app["url"])}" target="_blank">View posting</a>'
    st.markdown(f'<p class="ja-muted">{line}</p>', unsafe_allow_html=True)

    if flash := st.session_state.pop("rv_flash", None):
        st.warning(flash)

    if not drafts:
        st.info("There's no draft for this application yet. Generate one on the New cover letter screen.")
        return

    left, right = st.columns([3, 2], gap="large")
    with left:
        labels = {d["version"]: _version_label(d) for d in drafts}
        version = drafts[0]["version"]
        if len(drafts) > 1:
            version = st.selectbox("Version", list(labels), format_func=labels.get, key=f"rv_version_{app_id}")
        current = next(d for d in drafts if d["version"] == version)
        with st.container(border=True, key="card_letter"):
            st.caption(f"{pipeline.word_count(current['text'])} words")
            st.markdown(_md(current["text"]))
        with st.expander("Plain text to copy"):
            st.code(current["text"], language=None, wrap_lines=True)
        st.caption("Checking claims, editing, approval and export arrive in milestones 4 and 5.")

    with right:
        _summary_card(parsed)
        _match_card(app.get("match_json"))
        with st.expander("Saved job posting"):
            st.text(app.get("posting_text") or "")


def _version_label(draft: dict) -> str:
    when = datetime.fromisoformat(draft["created_at"])
    note = f'"{draft["feedback"]}"' if draft.get("feedback") else ("First draft" if draft["version"] == 1 else "New draft")
    return f"v{draft['version']} · {note} · {when:%b} {when.day}, {when.hour % 12 or 12}:{when:%M %p}"


def _summary_card(parsed: dict) -> None:
    with st.container(border=True, key="card_summary"):
        st.subheader("Posting summary", anchor=False)
        if parsed.get("contact_name"):
            st.markdown(f"**Addressed to:** {escape(parsed['contact_name'])}")
        if parsed.get("must_have"):
            st.markdown("**Must have**")
            st.markdown("\n".join(f"- {_md(x)}" for x in parsed["must_have"]))
        if parsed.get("nice_to_have"):
            st.markdown("**Nice to have**")
            st.markdown("\n".join(f"- {_md(x)}" for x in parsed["nice_to_have"]))


def _match_card(matches: dict | None) -> None:
    with st.container(border=True, key="card_match"):
        st.subheader("How you match", anchor=False)
        if not matches:
            st.caption("No match yet.")
            return
        for m in matches["matches"]:
            strength = m["strength"]
            sources = sorted({e["source"].capitalize() for e in m["evidence"]}) or ["Skipped"]
            featured = " · featured" if m["feature"] else ""
            st.markdown(
                f"{escape(m['requirement'])} "
                f'<span class="ja-strength ja-{strength}">{STRENGTH_LABEL[strength]}</span> '
                f'<span class="ja-muted" style="font-size:13px">{", ".join(sources)}{featured}</span>',
                unsafe_allow_html=True,
            )
            for e in m["evidence"]:
                st.caption(f"“{e['quote']}”")
