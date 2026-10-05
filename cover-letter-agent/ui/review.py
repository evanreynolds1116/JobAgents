"""Review and approve screen.

Shows the letter with unsupported claims and style flags highlighted, the
requirement match and the version history. You can edit the letter, ask for
changes, fix flags, and approve. Only the Approve button makes a letter final,
and any change after approval returns it to draft.
"""

import re
from html import escape
from pathlib import Path

import streamlit as st

from agent import lint, pipeline
from export import docx as exporter
from export.docx import can_export
from storage import db
from storage import profile as profile_store
from ui import dates, drafting, nav

STRENGTH_LABEL = {"strong": "Strong", "partial": "Partial", "none": "None"}


def _app_id() -> int | None:
    raw = st.query_params.get("app")
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def _md(text: str) -> str:
    """Plain text for st.markdown: keep single line breaks, stop $ becoming math."""
    return text.replace("$", r"\$").replace("\n", "  \n")


def _settings() -> pipeline.DraftSettings:
    saved = profile_store.load()
    return pipeline.DraftSettings(saved.tone, saved.length)


def _show_latest(app_id: int) -> None:
    st.session_state.pop(f"rv_version_{app_id}", None)
    st.session_state.pop("rv_editing", None)


def _run_step(label: str, work) -> None:
    """Run a slow step with a status box; errors are kept for the next run to show."""
    with st.status(label, expanded=True) as status:
        try:
            work(st.write)
        except pipeline.PipelineError as exc:
            status.update(label="That didn't finish", state="error")
            st.session_state.rv_error = (exc.message, exc.raw)
            st.rerun()
        status.update(label="Done", state="complete")


# --- Page ------------------------------------------------------------------------


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
    if not drafts:
        st.title(app.get("title") or "Review and approve")
        st.info("There's no draft for this application yet. Generate one on the New cover letter screen.")
        return
    latest = drafts[0]
    by_version = {d["version"]: d for d in drafts}
    viewing = by_version.get(st.session_state.get(f"rv_version_{app_id}"), latest)
    is_latest = viewing["version"] == latest["version"]
    approved = app["status"] in ("approved", "submitted")  # the approved letter is final

    _header(app, latest, approved)
    _messages()

    left, right = st.columns([3, 2], gap="large")
    with left:
        if not is_latest:
            _old_version_banner(app_id, viewing, latest)
        if st.session_state.get("rv_editing") and is_latest:
            _editor(app_id, viewing, approved)
        else:
            _letter_card(app_id, viewing, approved, editable=is_latest)
        _export_row(app)
        with st.expander("Plain text to copy"):
            st.code(viewing["text"], language=None, wrap_lines=True)

    with right:
        if is_latest and not approved:
            _review_card(app_id, latest)
        elif approved and is_latest:
            with st.container(border=True, key="card_approved"):
                st.markdown(f"**Approved** version {app['sent_version']} on {dates.full(app['approved_at'])}.")
                st.caption("Editing or redrafting returns the letter to draft.")
                if st.button("Application details"):
                    nav.go("detail", app=app_id)
        _ask_for_changes(app_id)
        _match_card(app.get("match_json"))
        _versions_card(app_id, drafts, viewing)
        _notes_card(app_id, app, latest)
        _posting_card(app)


def _header(app: dict, latest: dict, approved: bool) -> None:
    company = app.get("company") or "Unknown company"
    head, action = st.columns([3, 1], vertical_alignment="bottom")
    with head:
        st.markdown(f'<p class="ja-crumb">Applications › {escape(company)}</p>', unsafe_allow_html=True)
        st.title(app.get("title") or "Untitled job")
        chip = "ja-strong" if approved else "ja-partial"
        state = {"approved": "Approved", "submitted": "Submitted"}.get(app["status"], "Draft")
        version = app["sent_version"] if approved else latest["version"]
        parsed = app.get("parsed_json") or {}
        facts = [company] + ([parsed["location"]] if parsed.get("location") else [])
        line = " · ".join(escape(f) for f in facts)
        if app.get("url"):
            line += f' · <a href="{escape(app["url"])}" target="_blank">View posting</a>'
        st.markdown(
            f'<span class="ja-strength {chip}">{state} · version {version}</span> '
            f'<span class="ja-muted" style="margin-left:8px">{line}</span>',
            unsafe_allow_html=True,
        )
    with action:
        if approved:
            st.button(state_label(app), disabled=True, width="stretch", key="rv_approved_badge")
        else:
            _approve_button(app["id"], latest)


def state_label(app: dict) -> str:
    return "Submitted" if app["status"] == "submitted" else "Approved"


def _approve_button(app_id: int, latest: dict) -> None:
    needs_review = pipeline.flag_count(latest["verify_json"]) > 0 or not latest["verify_json"]
    reviewed = st.session_state.get(f"rv_reviewed_{app_id}_{latest['version']}", False)
    locked = needs_review and not reviewed
    if st.button("Approve letter", type="primary", disabled=locked, width="stretch", key="rv_approve"):
        db.approve(app_id, latest["version"])
        st.session_state.rv_success = "Approved. This version is now final, and you can export it below."
        st.rerun()
    if locked:
        st.caption("Review the flagged items first.")


def _messages() -> None:
    if flash := st.session_state.pop("rv_flash", None):
        st.warning(flash)
    if success := st.session_state.pop("rv_success", None):
        st.success(success)
    if error := st.session_state.pop("rv_error", None):
        message, raw = error
        st.error(f"**That didn't finish.** {message} Anything already done is saved.")
        if raw:
            with st.expander("Debug details"):
                st.code(raw, language=None, wrap_lines=True)


# --- Letter --------------------------------------------------------------------


def _find(text: str, part: str) -> tuple[int, int] | None:
    if not part.strip():
        return None
    straight = lint._straight(text).lower()
    i = straight.find(lint._straight(part).lower())
    return (i, i + len(part)) if i >= 0 else None


def _highlights(text: str, verify: dict | None) -> list[tuple[int, int, str, str]]:
    found = pipeline.flags(verify)
    marks = []
    for c in found["claims"]:
        if span := _find(text, c["claim"]):
            marks.append((*span, "ja-flag-claim", c["reason"] or "Not supported by your sources."))
    for f in found["style"]:
        if span := _find(text, f["text"]):
            marks.append((*span, "ja-flag-style", f["issue"]))
    for h in found["lint"]:
        if h["kind"] != "em_dash" and (span := _find(text, h["text"])):
            marks.append((*span, "ja-flag-style", h["message"]))
    marks.sort()
    kept, end = [], -1
    for m in marks:  # drop overlaps, keeping the earlier (claims come first at equal starts)
        if m[0] >= end:
            kept.append(m)
            end = m[1]
    return kept


def letter_html(text: str, verify: dict | None) -> str:
    """The letter as HTML with flagged spans highlighted; hover shows the reason."""
    out, pos = [], 0
    for start, end, cls, title in _highlights(text, verify):
        out.append(escape(text[pos:start]))
        out.append(f'<mark class="{cls}" title="{escape(title)}">{escape(text[start:end])}</mark>')
        pos = end
    out.append(escape(text[pos:]))
    body = "".join(out)
    paragraphs = [p.replace("\n", "<br>") for p in body.split("\n\n")]
    return '<div class="ja-letter">' + "".join(f"<p>{p}</p>" for p in paragraphs) + "</div>"


def _letter_card(app_id: int, draft: dict, approved: bool, editable: bool) -> None:
    with st.container(border=True, key="card_letter"):
        top, edit = st.columns([3, 1], vertical_alignment="center")
        top.caption(f"{pipeline.word_count(draft['text'])} words · version {draft['version']}")
        if editable and edit.button("Edit letter", width="stretch"):
            st.session_state.rv_editing = True
            st.session_state.rv_edit_text = draft["text"]
            st.rerun()
        st.markdown(letter_html(draft["text"], draft["verify_json"]), unsafe_allow_html=True)
    if editable and approved:
        st.caption("Editing the letter now would return it to draft.")
    elif editable:
        st.caption("Highlighted text needs your review: red for claims your sources don't support, "
                   "amber for style. Hover for the reason.")


def _editor(app_id: int, draft: dict, approved: bool) -> None:
    with st.container(border=True, key="card_editor"):
        st.text_area("Edit the letter", key="rv_edit_text", height=520)
        if approved:
            st.caption("Saving returns the letter to draft.")
        save, cancel, _ = st.columns([1, 1, 2])
        if save.button("Save edits", type="primary"):
            text = st.session_state.rv_edit_text.strip()
            if text and text != draft["text"]:
                _run_step("Saving your edits…", lambda say: drafting.save_edit(app_id, text, say=say))
            _show_latest(app_id)
            st.rerun()
        if cancel.button("Cancel"):
            st.session_state.pop("rv_editing", None)
            st.rerun()


def _old_version_banner(app_id: int, viewing: dict, latest: dict) -> None:
    with st.container(border=True, key="card_old_version"):
        st.markdown(f"You're viewing **version {viewing['version']}**. The latest is version {latest['version']}.")
        with st.container(horizontal=True):
            use = st.button("Use this version", type="primary")
            back = st.button("Back to latest")
        if use:
            db.save_version(app_id, viewing["text"], viewing["resume_hash"],
                            feedback=f"Restored version {viewing['version']}", verify=viewing["verify_json"])
            _show_latest(app_id)
            st.rerun()
        if back:
            _show_latest(app_id)
            st.rerun()


def _export_row(app: dict) -> None:
    unlocked = can_export(app)
    with st.container(horizontal=True):
        want_docx = st.button("Export .docx", disabled=not unlocked, key="rv_export_docx")
        want_pdf = st.button("Export PDF", disabled=not unlocked, key="rv_export_pdf")
        if st.button("Fill application", disabled=not unlocked, key="rv_fill",
                     help="Open the job's application form in Chrome and fill it from your profile. "
                          "The agent never submits."):
            nav.go("apply", app=app["id"])
    if not unlocked:
        st.caption("Export unlocks after you approve.")
        return
    key = f"rv_exported_{app['id']}"
    drafts = db.list_drafts(app["id"])
    if want_docx:
        st.session_state[key] = str(exporter.export_docx(app, drafts, profile_store.load()))
    if want_pdf:
        with st.spinner("Making the PDF with Microsoft Word…"):
            try:
                st.session_state[key] = str(exporter.export_pdf(app, drafts, profile_store.load()))
            except exporter.PdfUnavailable as exc:
                st.session_state[key] = str(exporter.export_docx(app, drafts, profile_store.load()))
                st.warning(str(exc))
    if saved := st.session_state.get(key):
        path = Path(saved)
        if path.exists():
            mime = ("application/pdf" if path.suffix == ".pdf" else
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.download_button(f"Download {path.name}", data=path.read_bytes(), file_name=path.name,
                               mime=mime, key=f"rv_download_{app['id']}")
            st.caption(f"Saved in the output folder: {path}")
    else:
        st.caption(f"Exports version {app['sent_version']}, the one you approved.")


# --- Review panel ---------------------------------------------------------------


def _sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """Expand a span to the whole sentence around it."""
    left = max(text.rfind(". ", 0, start), text.rfind("! ", 0, start), text.rfind("? ", 0, start),
               text.rfind("\n", 0, start))
    left = left + 1 if left >= 0 else 0
    match = re.search(r"[.!?](?=\s|$)", text[end - 1:])
    right = end - 1 + match.end() if match else len(text)
    return left, right  # the space before the sentence goes with it; the one after stays


def remove_sentence(text: str, claim: str) -> str:
    span = _find(text, claim)
    if not span:
        return text
    left, right = _sentence_bounds(text, *span)
    cut = text[:left] + text[right:]
    cut = re.sub(r"[ \t]{2,}", " ", cut)
    cut = re.sub(r" +\n", "\n", cut)
    cut = re.sub(r"\n +", "\n", cut)
    return re.sub(r"\n{3,}", "\n\n", cut).strip()


def _add_to_notes(app_id: int, app: dict, claim: str, version: int) -> None:
    notes = (app.get("user_notes") or "").rstrip()
    db.update_application(app_id, user_notes=(notes + "\n" if notes else "") + claim)
    _run_step("Checking the letter again…", lambda say: drafting.recheck(app_id, version))
    st.rerun()


def _review_card(app_id: int, latest: dict) -> None:
    app = db.get_application(app_id)
    verify = latest["verify_json"]
    found = pipeline.flags(verify)
    total = pipeline.flag_count(verify)
    with st.container(border=True, key="card_review"):
        if found["unchecked"]:
            st.subheader("Not checked yet", anchor=False)
            st.caption("This version hasn't been checked against your resume and notes.")
            if st.button("Check again", type="primary"):
                _run_step("Checking every claim…", lambda say: drafting.recheck(app_id, latest["version"]))
                st.rerun()
        elif total == 0:
            st.subheader("All clear", anchor=False)
            supported = len(verify["claims"])
            st.caption(f"All {supported} claims trace to your resume, profile, notes or the posting, "
                       "and no style issues were found.")
            return
        else:
            st.subheader(f"Needs your review ({total})", anchor=False)

        for i, c in enumerate(found["claims"]):
            st.markdown('<span class="ja-strength ja-none">Unsupported claim</span>', unsafe_allow_html=True)
            st.markdown(f"“{_md(c['claim'])}”")
            st.caption(c["reason"] or "Not supported by your resume, profile or notes.")
            with st.container(horizontal=True):
                remove = st.button("Remove sentence", key=f"rv_remove_{i}")
                true = st.button("It's true: add to notes", key=f"rv_true_{i}")
            if remove:
                new_text = remove_sentence(latest["text"], c["claim"])
                _run_step("Removing the sentence…",
                          lambda say: drafting.save_edit(app_id, new_text, label="Removed a sentence", say=say))
                _show_latest(app_id)
                st.rerun()
            if true:
                _add_to_notes(app_id, app, c["claim"], latest["version"])
        for i, f in enumerate(found["style"] + [
            {"text": h["text"], "issue": h["message"]} for h in found["lint"]
        ]):
            st.markdown('<span class="ja-strength ja-partial">Style</span>', unsafe_allow_html=True)
            if f["text"] != "—":
                st.markdown(f"“{_md(f['text'])}”")
            st.caption(f["issue"])
            if st.button("Rewrite this sentence", key=f"rv_rewrite_{i}"):
                feedback = f'Rewrite this part: "{f["text"]}". Problem: {f["issue"]}'
                _run_step("Rewriting…", lambda say: drafting.revise(app_id, feedback, _settings(), say=say))
                _show_latest(app_id)
                st.rerun()
        st.checkbox("I've reviewed the flagged items", key=f"rv_reviewed_{app_id}_{latest['version']}")


def _ask_for_changes(app_id: int) -> None:
    with st.container(border=True, key="card_changes"):
        st.subheader("Ask for changes", anchor=False)
        feedback = st.text_area("What should change?", key="rv_feedback", height=90,
                                placeholder='For example: "more formal" or "lead with the data project"',
                                label_visibility="collapsed")
        if st.button("Redraft", disabled=not feedback.strip()):
            _run_step("Redrafting…", lambda say: drafting.revise(app_id, feedback.strip(), _settings(), say=say))
            st.session_state.pop("rv_feedback", None)
            _show_latest(app_id)
            st.rerun()
        st.caption("Each redraft is saved as a new version. To add a fact, put it in the job notes below.")


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


def _version_label(draft: dict) -> str:
    note = f'"{draft["feedback"]}"' if draft.get("feedback") else ("First draft" if draft["version"] == 1 else "New draft")
    return f"v{draft['version']} · {note} · {dates.full(draft['created_at'])}"


def _versions_card(app_id: int, drafts: list[dict], viewing: dict) -> None:
    with st.container(border=True, key="card_versions"):
        st.subheader("Versions", anchor=False)
        labels = {d["version"]: _version_label(d) for d in drafts}
        st.radio("Version", list(labels), format_func=labels.get, key=f"rv_version_{app_id}",
                 index=list(labels).index(viewing["version"]), label_visibility="collapsed")


def _notes_card(app_id: int, app: dict, latest: dict) -> None:
    with st.expander("Notes for this job"):
        notes = st.text_area("Notes", value=app.get("user_notes") or "", key=f"rv_notes_{app_id}",
                             height=120, label_visibility="collapsed")
        st.caption("Facts here count as true, like your resume. After changing them, check the letter again.")
        if st.button("Save notes and check again", disabled=notes == (app.get("user_notes") or "")):
            db.update_application(app_id, user_notes=notes)
            _run_step("Checking the letter again…", lambda say: drafting.recheck(app_id, latest["version"]))
            st.rerun()


def _posting_card(app: dict) -> None:
    parsed = app.get("parsed_json") or {}
    with st.expander("Posting summary"):
        if parsed.get("contact_name"):
            st.markdown(f"**Addressed to:** {escape(parsed['contact_name'])}")
        for label, key in (("Must have", "must_have"), ("Nice to have", "nice_to_have")):
            if parsed.get(key):
                st.markdown(f"**{label}**")
                st.markdown("\n".join(f"- {_md(x)}" for x in parsed[key]))
    with st.expander("Saved job posting"):
        st.text(app.get("posting_text") or "")
