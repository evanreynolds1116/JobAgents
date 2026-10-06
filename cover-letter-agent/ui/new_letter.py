"""New cover letter screen: job link, notes, tone and length, then Generate draft.

Generating runs fetch -> parse -> match -> draft, saving after each step so a
failure never loses work; "Try again" picks up where it stopped.

Start letter on Find jobs opens this screen with ?job=<id>. A watch-list job already has
its full posting, so drafting starts right away. Adzuna doesn't let the app read its job
pages, so for those the link and paste box are set up for you.
"""

import streamlit as st

import config
from agent import fetch, pipeline
from storage import db, resume
from storage import jobs as job_store
from storage import profile as profile_store
from ui import drafting, nav

TRIMMED_NOTE = (
    "The posting was very long, so only its first {n:,} characters were used. "
    "Check that the requirements in the summary look complete."
)


def _init_state() -> None:
    if "nl_tone" not in st.session_state:
        saved = profile_store.load()
        st.session_state.nl_tone = saved.tone
        st.session_state.nl_length = saved.length


def _clear_status() -> None:
    for key in ("nl_fetch_error", "nl_duplicate", "nl_error", "nl_confirm", "nl_problem"):
        st.session_state.pop(key, None)


def _show_paste() -> None:
    st.session_state.nl_paste_mode = True


def posting_from_job(job: dict) -> str:
    """A watch-list job's stored posting, headed like a fetched page's."""
    head = [f"Job title: {job['title']}", f"Company: {job['company']}"]
    if job["location"]:
        head.append(f"Location: {job['location']}")
    return "\n".join(head) + "\n\n" + (job["description"] or "")


def _from_job(job_id: int) -> None:
    """Set up the screen once for a job sent from Find jobs."""
    if st.session_state.get("nl_job_loaded") == job_id:
        return
    st.session_state.nl_job_loaded = job_id
    job = job_store.get_job(job_id)
    if not job:
        return
    _clear_status()
    if job["source"] != "adzuna" and len(job["description"] or "") >= fetch.MIN_CHARS:
        text, trimmed = fetch.trim(posting_from_job(job))
        app_id = db.create_application(job["apply_url"] or None, text)
        db.update_application(app_id, job_id=job_id)
        job_store.set_status(job_id, "applying")
        if trimmed:
            st.session_state.rv_flash = TRIMMED_NOTE.format(n=fetch.MAX_CHARS)
        _run(app_id)
        return
    st.session_state.nl_job = job_id
    st.session_state.nl_url = job["apply_url"] or ""
    st.session_state.nl_paste_mode = True
    st.session_state.nl_paste = ""


def _draft_for(app_id: int) -> None:
    """Draft a letter for an application that already has its posting (for example, one the
    form filler found needs a letter)."""
    if st.session_state.get("nl_draft_loaded") == app_id:
        return
    st.session_state.nl_draft_loaded = app_id
    if db.get_application(app_id):
        _clear_status()
        _run(app_id)


def _fill_without_letter() -> None:
    """Save the link as an application with no letter and open the form filler."""
    url = (st.session_state.get("nl_url") or "").strip()
    if not url:
        st.session_state.nl_problem = "Add the job posting link first."
        st.rerun()
    if existing := db.find_by_url(url):
        nav.go("apply", app=existing["id"])
    with st.spinner("Saving the posting…"):
        result = fetch.fetch(url)
    text = result.text if result.ok else ""
    app_id = db.create_application(url, text, st.session_state.get("nl_notes", ""))
    # The page's own job data when it has some (even if the rest couldn't be read), else a
    # guess from the link. Both can be corrected on the Fill application screen.
    company = result.hints.get("company") or fetch.company_from_url(url)
    db.update_application(app_id, company=company, title=result.hints.get("title"))
    nav.go("apply", app=app_id)


def _job_note() -> None:
    job = job_store.get_job(st.session_state.nl_job)
    if not job:
        return
    label = " at ".join(x for x in (job["title"], job["company"]) if x)
    link = f"[Open the posting]({job['apply_url']})" if job["apply_url"] else "Open the posting"
    st.info(f"**{label}**, from Find jobs. Adzuna doesn't let the app read its job pages, so {link[0].lower()}"
            f"{link[1:]}, copy the whole posting and paste it below. Then click Generate draft.")


def new_letter_page() -> None:
    _init_state()
    st.markdown('<p class="ja-crumb">Cover letter agent</p>', unsafe_allow_html=True)
    st.title("New cover letter")

    if not resume.has_resume():
        with st.container(border=True, key="card_no_resume"):
            st.markdown("**Add your resume first.** Letters are built from it, so drafting needs it.")
            if st.button("Go to Profile & resume", type="primary"):
                nav.go("profile")
        return

    if draft_for := st.query_params.get("draft"):
        _draft_for(int(draft_for))
    if job_id := st.query_params.get("job"):
        _from_job(int(job_id))
    else:  # opened from the sidebar: a job from an earlier visit no longer applies
        for key in ("nl_job", "nl_job_loaded"):
            st.session_state.pop(key, None)

    if st.session_state.get("nl_confirm"):
        _confirm_card(st.session_state.nl_confirm)
        return
    _status_messages()
    if st.session_state.get("nl_job"):
        _job_note()

    form, aside = st.columns([5, 2], gap="large")
    with form, st.container(border=True, key="card_letter_setup"):
        st.text_input("Job posting link", key="nl_url", placeholder="https://careers.example.com/jobs/123")
        st.caption("Use the company's own posting, not a LinkedIn, Indeed or Jobright page.")
        if not st.session_state.get("nl_paste_mode"):
            st.button("Paste the posting text instead", type="tertiary", on_click=_show_paste)
        if st.session_state.get("nl_paste_mode"):
            st.text_area(
                "Posting text",
                key="nl_paste",
                height=220,
                placeholder="Copy the whole job posting from the page and paste it here.",
                help="If you also give the link above, it's saved with the application for your records.",
            )
        st.text_area(
            "Notes for this job (optional)",
            key="nl_notes",
            height=120,
            placeholder="For example: I'm a lifelong hockey fan and play in a weekly league. Lead with that.",
        )
        st.caption(
            "Anything that isn't on your resume but matters for this job, or instructions like "
            '"emphasize leadership". The agent treats these as true facts from you.'
        )
        tone, length = st.columns(2)
        tone.selectbox("Tone", profile_store.TONES, key="nl_tone")
        length.selectbox("Length", profile_store.LENGTHS, key="nl_length")
        with st.container(horizontal=True):
            if st.button("Generate draft", type="primary"):
                _clear_status()
                _start()
            if st.button("Fill without a letter", key="nl_fill_only",
                         help="Skip the cover letter and open the application form in Chrome. The agent never "
                              "submits."):
                _clear_status()
                _fill_without_letter()

    with aside, st.container(border=True, key="card_next"):
        st.subheader("What happens next", anchor=False)
        st.markdown(
            "1. Fetch the full posting. If the site blocks it, you'll be asked to paste the text.\n"
            "2. Pull out the requirements and match them to your resume and notes.\n"
            "3. Draft the letter in your voice, using your writing sample.\n"
            "4. Rewrite stiff phrasing and trim to your length, check every claim against your resume "
            "and notes, and fix any that don't hold up.\n"
            "5. You review, edit and approve."
        )
        st.caption("Usually one to two minutes.")


def _status_messages() -> None:
    if reason := st.session_state.get("nl_fetch_error"):
        st.warning(f"**Couldn't read this page.** {reason} Paste the posting text below; the link is kept for your records.")
    if problem := st.session_state.get("nl_problem"):
        st.error(problem)
    if app_id := st.session_state.get("nl_duplicate"):
        existing = db.get_application(app_id)
        label = " at ".join(x for x in (existing.get("title"), existing.get("company")) if x) or "this posting"
        with st.container(border=True, key="card_duplicate"):
            st.markdown(f"**You already have an application for {label}.**")
            st.caption("Open it, or draft a new version using the saved posting and the notes below.")
            open_col, again_col, _ = st.columns([1, 1, 2])
            if open_col.button("Open it", type="primary"):
                _clear_status()
                nav.go("review", app=app_id)
            if again_col.button("Draft a new version"):
                _clear_status()
                db.update_application(app_id, user_notes=st.session_state.get("nl_notes", ""), match_json=None)
                _run(app_id)
    if error := st.session_state.get("nl_error"):
        app_id, message, raw = error
        st.error(f"**Drafting stopped.** {message} Your posting and any finished steps are saved.")
        if st.button("Try again", type="primary"):
            _clear_status()
            _run(app_id)
        if raw:
            with st.expander("Debug details"):
                st.code(raw, language=None, wrap_lines=True)


def _start() -> None:
    url = (st.session_state.get("nl_url") or "").strip()
    pasted = (st.session_state.get("nl_paste") or "").strip() if st.session_state.get("nl_paste_mode") else ""
    notes = st.session_state.get("nl_notes", "")
    if not url and not pasted:
        st.session_state.nl_problem = "Add a job posting link, or paste the posting text."
        st.rerun()

    if url and (existing := db.find_by_url(url)):
        st.session_state.nl_duplicate = existing["id"]
        st.rerun()

    if pasted:
        text, trimmed = fetch.trim(pasted)
    else:
        with st.spinner("Reading the posting…"):
            result = fetch.fetch(url)
        if not result.ok:
            st.session_state.nl_fetch_error = result.reason
            st.session_state.nl_paste_mode = True
            st.rerun()
        text, trimmed = result.text, result.trimmed
    if len(text) < 200:
        st.session_state.nl_problem = "That posting text is too short to work from. Paste the whole posting."
        st.rerun()

    app_id = db.create_application(url or None, text, notes)
    if job_id := st.session_state.pop("nl_job", None):
        db.update_application(app_id, job_id=job_id)
        job_store.set_status(job_id, "applying")
    if trimmed:
        st.session_state.rv_flash = TRIMMED_NOTE.format(n=fetch.MAX_CHARS)
    _run(app_id)


def _confirm_card(app_id: int) -> None:
    app = db.get_application(app_id)
    parsed = app["parsed_json"]
    with st.container(border=True, key="card_confirm"):
        st.subheader("Check the company and job title", anchor=False)
        if parsed.get("several_jobs"):
            st.caption("This page seems to list more than one job. Enter the one you're applying for.")
        else:
            st.caption("The posting didn't make these clear. Confirm or correct them before drafting.")
        company = st.text_input("Company", value=parsed.get("company") or "", key="nl_confirm_company")
        title = st.text_input("Job title", value=parsed.get("title") or "", key="nl_confirm_title")
        go_col, cancel_col, _ = st.columns([1, 1, 2])
        if go_col.button("Continue drafting", type="primary", disabled=not (company.strip() and title.strip())):
            parsed.update(company=company.strip(), title=title.strip(), several_jobs=False)
            db.update_application(app_id, parsed_json=parsed, company=parsed["company"], title=parsed["title"])
            st.session_state.pop("nl_confirm", None)
            _run(app_id)
        if cancel_col.button("Start over"):
            st.session_state.pop("nl_confirm", None)
            st.rerun()


def _run(app_id: int) -> None:
    """Run whichever steps haven't finished yet, then open the review screen."""
    settings = config.load_settings()
    client = pipeline.make_client(settings.api_key)
    app = db.get_application(app_id)
    resume_text = resume.load_text()
    notes = app.get("user_notes") or ""

    with st.status("Drafting your letter…", expanded=True) as status:
        try:
            parsed = app.get("parsed_json")
            if not parsed:
                st.write("Reading the job's requirements…")
                parsed = pipeline.parse_job(client, settings.model, app["posting_text"])
                db.update_application(app_id, parsed_json=parsed, company=parsed["company"], title=parsed["title"])
                if pipeline.needs_confirmation(parsed):
                    status.update(label="Check the company and title", state="complete")
                    st.session_state.nl_confirm = app_id
                    st.rerun()
            matches = app.get("match_json")
            if not matches:
                st.write("Matching them to your resume and notes…")
                matches = pipeline.match(client, settings.model, parsed, resume_text, notes)
                db.update_application(app_id, match_json=matches)
            st.write("Writing the draft…")
            draft_settings = pipeline.DraftSettings(st.session_state.get("nl_tone"), st.session_state.get("nl_length"))
            letter = pipeline.draft(client, settings.model, parsed, matches, resume_text, notes,
                                    profile_store.load(), draft_settings)
        except pipeline.PipelineError as exc:
            status.update(label="Drafting stopped", state="error")
            st.session_state.nl_error = (app_id, exc.message, exc.raw)
            st.rerun()
        try:
            drafting.finish(app_id, letter, draft_settings, say=st.write)
        except pipeline.PipelineError as exc:  # the draft is saved, just not checked
            st.session_state.rv_flash = (
                f"The draft is saved, but it couldn't be checked yet. {exc.message} "
                "Use **Check again** below."
            )
        status.update(label="Draft ready", state="complete")
    nav.go("review", app=app_id)
