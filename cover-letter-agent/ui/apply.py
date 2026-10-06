"""Filling application screen (spec: Phase 2, How it works; mockup Apply.dc.html).

Shows where the session is, how the agent reached the form, and every field with what the
agent entered, where it came from and its status. The session itself runs in its own thread
(apply/session.py); this screen sends it commands and refreshes while it works.
"""

from html import escape

import streamlit as st

from apply import session, start
from storage import answers as answer_store
from storage import db
from ui import nav

BUSY = ("starting", "finding", "filling")
FINISHED = ("done", "stopped", "blocked", "error", "closed")
STATUS = {"filled": "Filled", "review": "Review", "needs_you": "Needs you", "left_for_you": "Left for you",
          "you": "Your edit"}
SOURCE = {"profile": "Your profile", "application_answers": "Application answers", "saved_answer": "Saved answer",
          "resume": "Your resume", "cover_letter": "Approved letter", "drafted": "Drafted for you", "none": "",
          "you": "You", "self_id": "Self-identification"}


def _app_id() -> int | None:
    try:
        return int(st.query_params.get("app", ""))
    except ValueError:
        return None


def summary(rows: list[dict]) -> str:
    """'5 filled · 1 to review · 2 left for you'"""
    counts = {key: sum(1 for r in rows if r["status"] == key) for key in STATUS}
    parts = [f"{counts['filled']} filled"]
    if counts["review"]:
        parts.append(f"{counts['review']} to review")
    left = counts["needs_you"] + counts["left_for_you"]
    if left:
        parts.append(f"{left} left for you")
    return " · ".join(parts)


def progress(snap: dict) -> str:
    """'✓ Page 1 · My Information' lines for a multi-page form, then where it is now."""
    lines = []
    for number, title in sorted(snap.get("titles", {}).items(), key=lambda kv: int(kv[0])):
        name = f"Page {number}" + (f" · {title}" if title else "")
        if int(number) in snap.get("pages_done", []):
            lines.append(f"- ✓ {escape(name)}")
        elif int(number) == snap["page"]:
            lines.append(f"- **Now:** {escape(name)}")
    return "\n".join(lines)


def apply_page() -> None:
    app_id = _app_id()
    app = db.get_application(app_id) if app_id else None
    if not app:
        st.title("Filling application")
        st.info("Open an application with an approved cover letter and click Fill application.")
        return
    st.markdown(f'<p class="ja-crumb">Applications › {escape(app.get("company") or "Application")}</p>',
                unsafe_allow_html=True)
    st.title("Filling application")
    current = session.current()
    if current is None or current.app_id != app_id or (not current.active and
                                                         current.snapshot()["state"] == "closed"):
        _not_started(app)
        return
    _live(app_id)


def _not_started(app: dict) -> None:
    st.caption(" · ".join(x for x in (app.get("title"), app.get("url")) if x))
    with st.container(border=True, key="card_fill_start"):
        st.markdown("A Chrome window opens with the app's own profile. The agent finds the application form, "
                    "asks you to confirm it, fills what it can from your profile, resume, application answers "
                    "and approved letter, drafts short screening answers for you to check, and pauses for you to "
                    "review. **It never clicks Submit.** You log in and solve any CAPTCHA yourself.")
        if not start.has_letter(app):
            st.caption("No approved cover letter: the form is filled without one. If it requires a letter, the agent "
                       "pauses and offers to draft one.")
        found = start.problems(app)
        for problem in found:
            st.warning(problem)
        other = session.current()
        busy = other is not None and other.active and other.app_id != app["id"]
        if busy:
            st.warning("Another application is being filled. Close its browser window first.")
        if st.button("Open the form", type="primary", disabled=bool(found) or busy, key="ap_start"):
            try:
                with st.spinner("Preparing your files…"):
                    session.start(start.prepare(app["id"]))
            except (start.StartProblem, RuntimeError) as exc:
                st.error(str(exc))
            else:
                st.rerun()


def _offers(offers: list[dict]) -> None:
    """Answers you typed that the agent didn't have: save them for later applications?"""
    handled = st.session_state.setdefault("ap_offers_done", set())
    for i, offer in enumerate(o for o in offers if o["label"] not in handled):
        with st.container(border=True, key=f"ap_offer_{i}"):
            st.markdown(f"You typed an answer for **{escape(offer['label'])}**: “{escape(str(offer['value']))}”. "
                        "Save it for future applications?", unsafe_allow_html=True)
            with st.container(horizontal=True):
                if st.button("Save answer", type="primary", key=f"ap_offer_save_{i}"):
                    answer_store.save(offer["label"], str(offer["value"]))
                    handled.add(offer["label"])
                    st.rerun()
                if st.button("Not now", key=f"ap_offer_skip_{i}"):
                    handled.add(offer["label"])
                    st.rerun()


def _other_link(app_id: int, current) -> None:
    """When a job board or a blocked site stops the agent: use the company's own link."""
    with st.container(border=True, key="ap_other_link"):
        link = st.text_input("Company's link for this job", key="ap_new_url",
                             placeholder="https://job-boards.greenhouse.io/company/jobs/123")
        if st.button("Use this link", key="ap_use_link", disabled=not link.strip()):
            url = link.strip() if "://" in link else f"https://{link.strip()}"
            db.update_application(app_id, url=url)
            current.send("close")
            st.session_state.pop("ap_new_url", None)
            st.rerun()


@st.fragment(run_every=1.5)
def _live(app_id: int) -> None:
    current = session.current()
    if current is None or current.app_id != app_id:
        st.rerun()
    snap = current.snapshot()
    state = snap["state"]
    platform = f" · {snap['platform']} form" if snap["platform"] else ""
    title = snap.get("titles", {}).get(str(snap["page"]), "")
    st.caption(f"{db.get_application(app_id).get('title') or ''}{platform} · page {snap['page']}"
               + (f" · {title}" if title else ""))

    with st.container(horizontal=True, key="ap_actions"):
        if state == "confirm" and st.button("Confirm form", type="primary", key="ap_confirm"):
            current.send("confirm")
        if state == "login" and st.button("Resume", type="primary", key="ap_resume"):
            current.send("resume")
        if state == "review" and st.button(f"Continue from page {snap['page']}", type="primary", key="ap_continue"):
            current.send("continue")
        if state == "needs_letter":
            if st.button("Draft a cover letter", type="primary", key="ap_draft_letter"):
                current.send("close")
                nav.go("new_letter", draft=app_id)
            if st.button("Fill without it", key="ap_skip_letter"):
                current.send("skip_letter")
        if state in ("confirm", "login", "review", "needs_letter") and st.button("Stop filling", key="ap_stop"):
            current.send("stop")
        if state in FINISHED and state != "closed" and st.button("Close browser", key="ap_close"):
            current.send("close")
        if state in FINISHED and st.button("Back to application", key="ap_back"):
            nav.go("detail", app=app_id)

    kind = {"error": st.error, "blocked": st.warning, "done": st.success}.get(state, st.info)
    kind(snap["message"] + (f"\n\n{snap['error']}" if snap["error"] else ""))
    if state == "blocked":
        _other_link(app_id, current)
    _offers(snap.get("offers", []))

    if len(snap.get("titles", {})) > 1 or snap.get("pages_done"):
        st.markdown(progress(snap))

    if snap["steps"]:
        with st.container(border=True, key="ap_route"):
            st.markdown("**How it got here**")
            st.markdown(" → ".join(escape(s) for s in snap["steps"]))

    if snap["rows"]:
        with st.container(border=True, key="ap_fields"):
            st.markdown(f"**Page {snap['page']} fields**  \n"
                        f'<span class="ja-muted">{summary(snap["rows"])}</span>', unsafe_allow_html=True)
            st.dataframe(
                [{"Field": r["label"] + (" *" if r["required"] else ""),
                  "What the agent entered": r["value"] if r["value"] else (r["note"] or "Left blank"),
                  "Source": SOURCE.get(r["source"], r["source"]) or (r["note"] if r["value"] else ""),
                  "Status": STATUS.get(r["status"], r["status"])} for r in snap["rows"]],
                hide_index=True, width="stretch")
            st.caption("Fields to review are outlined in amber in the browser; required fields left for you are "
                       "outlined in red.")
