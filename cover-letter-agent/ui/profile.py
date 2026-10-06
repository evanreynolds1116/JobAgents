"""Profile & resume screen (Milestone 2; company watch list, Milestone 12; application
answers and saved answers, Milestone 6)."""

from dataclasses import fields

import streamlit as st

import config
from agent import lint
from search import watchlist
from storage import answers as answer_store
from storage import application_profile as app_store
from storage import jobs as job_store
from storage import profile as profile_store
from storage import resume
from storage import self_id as self_id_store
from ui.style import muted

APP_FIELDS = tuple(f.name for f in fields(app_store.ApplicationProfile))
SELF_ID_FIELDS = tuple(f.name for f in fields(self_id_store.SelfId))
NOT_SET = "Not set"


def _choice(label: str, field: str, options: tuple[str, ...], column, help: str | None = None) -> None:
    column.selectbox(label, options, key=f"pf_app_{field}", format_func=lambda o: o or NOT_SET, help=help)


def _application_answers() -> None:
    with st.container(border=True, key="card_app_answers"):
        st.subheader("Application answers", anchor=False)
        st.caption("The application agent fills these in. It never answers legal attestations. Anything left "
                   "blank or Not set is left for you to answer on the form.")
        a, b = st.columns(2)
        _choice("Authorized to work in the US", "work_authorized", app_store.YES_NO, a)
        _choice("Need visa sponsorship", "needs_sponsorship", app_store.YES_NO, b,
                help="Now or in the future, as most forms ask it.")
        a, b = st.columns(2)
        _choice("Willing to relocate", "relocation", app_store.RELOCATION, a)
        b.text_input("Earliest start", key="pf_app_start_date", placeholder="Two weeks after an offer")
        st.text_input("How you usually hear about jobs", key="pf_app_heard_about", placeholder="Company website")
        st.text_input("Salary answer (optional)", key="pf_app_salary",
                      placeholder="Leave blank to answer it yourself each time")
        st.markdown("**Mailing address**")
        st.text_input("Street address", key="pf_app_street", placeholder="123 Main St")
        st.text_input("Apartment, suite, etc. (optional)", key="pf_app_street2")
        city, state, postal = st.columns([3, 2, 2])
        city.text_input("City", key="pf_app_city", placeholder="Nashville")
        state.text_input("State", key="pf_app_state", placeholder="TN")
        postal.text_input("ZIP code", key="pf_app_postal_code", placeholder="37203")
        st.text_input("Country", key="pf_app_country")


def _self_identification() -> None:
    with st.container(border=True, key="card_self_id"):
        st.subheader("Self-identification (optional)", anchor=False)
        st.caption("For the voluntary demographic and EEO questions many forms ask. Stored only on this computer "
                   "and never sent to Claude: the agent picks the matching option with plain code. Anything Not "
                   "set, or an answer that doesn't match one of a form's options, is left for you.")
        a, b = st.columns(2)
        a.selectbox("Gender", self_id_store.GENDER, key="pf_sid_gender", format_func=lambda o: o or NOT_SET)
        b.selectbox("Transgender", self_id_store.YES_NO, key="pf_sid_transgender", format_func=lambda o: o or NOT_SET)
        a, b = st.columns(2)
        a.selectbox("Sexual orientation", self_id_store.ORIENTATION, key="pf_sid_sexual_orientation",
                    format_func=lambda o: o or NOT_SET)
        b.text_input("Pronouns", key="pf_sid_pronouns", placeholder="she/her")
        a, b = st.columns(2)
        a.selectbox("Race", self_id_store.RACE, key="pf_sid_race", format_func=lambda o: o or NOT_SET)
        b.selectbox("Hispanic or Latino", self_id_store.YES_NO, key="pf_sid_hispanic_latino",
                    format_func=lambda o: o or NOT_SET, help="Many forms ask this separately from race.")
        a, b = st.columns(2)
        a.selectbox("Veteran status", self_id_store.VETERAN, key="pf_sid_veteran", format_func=lambda o: o or NOT_SET,
                    help="Protected veterans are defined by VEVRAA; most forms explain the categories.")
        b.selectbox("Disability", self_id_store.YES_NO, key="pf_sid_disability", format_func=lambda o: o or NOT_SET,
                    help="Yes if you have, or have had, a disability, as the standard form asks it.")


def _save_answer(answer_id: int | None) -> None:
    suffix = answer_id or "new"
    try:
        answer_store.save(st.session_state.get(f"pf_ans_q_{suffix}", ""),
                          st.session_state.get(f"pf_ans_a_{suffix}", ""), answer_id)
    except answer_store.AnswerError as exc:
        st.session_state.pf_ans_msg = ("warning", str(exc))
        return
    if answer_id is None:
        st.session_state.pf_ans_q_new = st.session_state.pf_ans_a_new = ""
    st.session_state.pf_ans_msg = ("success", "Answer saved.")


def _saved_answers() -> None:
    saved = answer_store.list_answers()
    with st.container(border=True, key="card_saved_answers"):
        st.subheader("Saved answers to past questions", anchor=False)
        st.caption(f"{len(saved)} saved. Answers you've approved for questions on past applications, reused "
                   "when a form asks something similar.")
        with st.expander("Manage"):
            for row in saved:
                with st.container(border=True, key=f"pf_ans_row_{row['id']}"):
                    st.text_input("Question", value=row["question"], key=f"pf_ans_q_{row['id']}")
                    st.text_area("Answer", value=row["answer"], key=f"pf_ans_a_{row['id']}", height=80)
                    used, save, delete = st.columns([3, 1, 1], vertical_alignment="center")
                    used.caption(f"Used {row['times_used']} time{'s' if row['times_used'] != 1 else ''}")
                    save.button("Save", key=f"pf_ans_save_{row['id']}", on_click=_save_answer, args=(row["id"],))
                    if delete.button("Delete", key=f"pf_ans_del_{row['id']}"):
                        answer_store.delete(row["id"])
                        st.session_state.pf_ans_msg = ("success", "Answer deleted.")
                        st.rerun()
            st.markdown("**Add an answer**")
            st.text_input("Question", key="pf_ans_q_new", placeholder="Why do you want to work here?")
            st.text_area("Answer", key="pf_ans_a_new", height=80)
            st.button("Add answer", key="pf_ans_add", on_click=_save_answer, args=(None,))
            if msg := st.session_state.pop("pf_ans_msg", None):
                getattr(st, msg[0])(msg[1])


def _add_company() -> None:
    """Check the careers link with one call to its board, then save the company."""
    link = st.session_state.get("pf_watch_link", "").strip()
    board = watchlist.parse_board(link) if link else None
    if not board:
        st.session_state.pf_watch_msg = ("warning", "Use a Greenhouse, Lever or Ashby careers link, for example "
                                         "job-boards.greenhouse.io/acme, jobs.lever.co/acme or jobs.ashbyhq.com/acme.")
        return
    try:
        raws = watchlist.fetch_board(board.platform, board.board)
    except watchlist.WatchError as exc:
        st.session_state.pf_watch_msg = ("warning", f"Couldn't add it: {exc}")
        return
    name = (st.session_state.get("pf_watch_name", "").strip()
            or next((r.get("company_name") for r in raws if r.get("company_name")), None)
            or board.board.replace("-", " ").title())
    job_store.add_company(name, board.platform, board.board)
    st.session_state.pf_watch_link = st.session_state.pf_watch_name = ""
    st.session_state.pf_watch_msg = ("success", f"Added {name} ({watchlist.PLATFORMS[board.platform]}, "
                                     f"{len(raws)} open job{'s' if len(raws) != 1 else ''}).")


def _watch_list() -> None:
    with st.container(border=True, key="card_watch"):
        st.subheader("Company watch list", anchor=False)
        st.caption("Companies whose own job boards are checked on every search, with full job descriptions. "
                   "Jobs are matched to your searches by title.")
        for company in job_store.list_companies():
            name, remove = st.columns([4, 1], vertical_alignment="center")
            name.markdown(f"{company['name']} "
                          f'<span class="ja-muted">· {watchlist.PLATFORMS[company["platform"]]}</span>',
                          unsafe_allow_html=True)
            if remove.button("Remove", key=f"pf_watch_remove_{company['id']}"):
                job_store.delete_company(company["id"])
                st.rerun()
        link, name = st.columns([3, 2])
        link.text_input("Careers page link", key="pf_watch_link", placeholder="https://jobs.lever.co/acme")
        name.text_input("Company name (optional)", key="pf_watch_name")
        st.button("Add company", on_click=_add_company)
        if msg := st.session_state.pop("pf_watch_msg", None):
            getattr(st, msg[0])(msg[1])

PROFILE_FIELDS = ("name", "email", "country_code", "phone", "city", "linkedin", "portfolio",
                  "tone", "length", "sign_off", "always_mention", "never_mention")


def _load_profile_state() -> None:
    """Fill the form from disk. Streamlit drops widget state when you leave the page,
    so this runs again on every visit and shows what's saved."""
    if "pf_name" in st.session_state:
        return
    saved = profile_store.load()
    for name in PROFILE_FIELDS:
        st.session_state[f"pf_{name}"] = getattr(saved, name)
    samples = saved.writing_samples or [""]
    st.session_state.pf_sample_count = len(samples)
    for i, sample in enumerate(samples):
        st.session_state[f"pf_sample_{i}"] = sample
    st.session_state.pf_resume_text = resume.load_text()
    saved_app = app_store.load()
    for name in APP_FIELDS:
        st.session_state[f"pf_app_{name}"] = getattr(saved_app, name)
    saved_sid = self_id_store.load()
    for name in SELF_ID_FIELDS:
        st.session_state[f"pf_sid_{name}"] = getattr(saved_sid, name)


def _app_from_state() -> app_store.ApplicationProfile:
    return app_store.ApplicationProfile(**{n: st.session_state.get(f"pf_app_{n}", "") for n in APP_FIELDS})


def _self_id_from_state() -> self_id_store.SelfId:
    return self_id_store.SelfId(**{n: st.session_state.get(f"pf_sid_{n}", "") for n in SELF_ID_FIELDS})


def _profile_from_state() -> profile_store.Profile:
    values = {name: st.session_state.get(f"pf_{name}", "") for name in PROFILE_FIELDS}
    values["country_code"] = profile_store.normalize_country_code(values["country_code"])
    samples = [st.session_state.get(f"pf_sample_{i}", "")
               for i in range(st.session_state.get("pf_sample_count", 1))]
    return profile_store.Profile(**values, writing_samples=[s for s in samples if s.strip()])


def _has_unsaved_changes() -> bool:
    if (_profile_from_state() != profile_store.load() or _app_from_state() != app_store.load()
            or _self_id_from_state() != self_id_store.load()):
        return True
    return st.session_state.get("pf_resume_text", "").strip() != resume.load_text().strip()


def _save_profile() -> None:
    current = _profile_from_state()
    profile_store.save(current)
    st.session_state.pf_country_code = current.country_code  # show "+44", not "44"
    resume.save_text(st.session_state.get("pf_resume_text", ""))
    answers = _app_from_state()
    app_store.save(answers)
    self_id_store.save(_self_id_from_state())
    st.session_state.pf_flash = ("success", "Saved.")
    st.session_state.pf_problems = current.problems() + answers.problems()


def _import_resume() -> None:
    key = f"pf_upload_{st.session_state.get('pf_upload_n', 0)}"
    upload = st.session_state.get(key)
    if upload is None:
        return
    try:
        text = resume.import_file(upload.name, upload.getvalue())
    except resume.ConversionError as exc:
        st.session_state.pf_flash = ("error", str(exc))
    else:
        st.session_state.pf_resume_text = text
        st.session_state.pf_flash = (
            "info",
            f"Converted **{upload.name}**. Check the text below for anything missing, "
            "fix it if needed, then click **Save changes**.",
        )
    st.session_state.pf_upload_n = st.session_state.get("pf_upload_n", 0) + 1  # clears the uploader


def _save_phrases() -> None:
    lint.save_phrases(st.session_state.get("pf_phrases", "").splitlines())
    st.session_state.pf_flash = ("success", "Banned-phrase list saved.")


def _add_sample() -> None:
    n = st.session_state.get("pf_sample_count", 1)
    st.session_state[f"pf_sample_{n}"] = ""
    st.session_state.pf_sample_count = n + 1


def _resume_uploader(label: str) -> None:
    st.file_uploader(
        label,
        type=["pdf", "docx"],
        key=f"pf_upload_{st.session_state.get('pf_upload_n', 0)}",
        on_change=_import_resume,
    )


def profile_page() -> None:
    _load_profile_state()

    head, action = st.columns([3, 1], vertical_alignment="bottom")
    with head:
        st.title("Profile & resume")
        muted("Used by all three agents. Stored only on this computer.")
    with action:
        st.button("Save changes", type="primary", on_click=_save_profile, width="stretch")
        if _has_unsaved_changes():
            st.caption("You have unsaved changes.")

    flash = st.session_state.pop("pf_flash", None)
    if flash:
        kind, message = flash
        getattr(st, kind)(message)
    for problem in st.session_state.pop("pf_problems", []):
        st.warning(problem)

    left, right = st.columns(2, gap="large")

    with left:
        with st.container(border=True, key="card_resume"):
            st.subheader("Resume", anchor=False)
            original = resume.original_info()
            if original:
                name, uploaded = original
                file_col, replace_col = st.columns([2, 1], vertical_alignment="center")
                file_col.markdown(
                    f'<span class="ja-file">{name} <span class="ja-muted">· uploaded '
                    f'{uploaded:%b} {uploaded.day}</span></span>',
                    unsafe_allow_html=True,
                )
                with replace_col.popover("Replace", width="stretch"):
                    st.caption(
                        "The new file is converted and replaces the text below, "
                        "including any edits you made."
                    )
                    _resume_uploader("Upload a new PDF or .docx")
            else:
                _resume_uploader("Upload your resume (PDF or .docx)")
                st.caption("Or paste your resume as text below.")
            st.text_area(
                "Converted text (check nothing is missing)",
                key="pf_resume_text",
                height=420,
                placeholder="Your resume text appears here after upload, so you can fix "
                "anything the conversion missed.",
            )

        with st.container(border=True, key="card_writing"):
            st.subheader("Writing sample", anchor=False)
            st.caption(
                "A past cover letter or a long email you wrote. Drafts match its "
                "vocabulary, sentence length and formality."
            )
            count = st.session_state.get("pf_sample_count", 1)
            for i in range(count):
                st.text_area(
                    f"Writing sample {i + 1}",
                    key=f"pf_sample_{i}",
                    height=180,
                    placeholder="Paste your writing here",
                    label_visibility="collapsed" if count == 1 else "visible",
                )
            st.button("Add another sample", on_click=_add_sample)
            if count > 1:
                st.caption("To remove a sample, clear its text and save.")
            phrases = lint.load_phrases()
            count_col, edit_col = st.columns([2, 1], vertical_alignment="center")
            count_col.markdown(f"Banned phrases: {len(phrases)}")
            with edit_col.popover("Edit list", width="stretch"):
                st.caption("One per line, any capitalization. Drafts avoid these, and any left over are flagged.")
                st.text_area("Banned phrases", value="\n".join(phrases), key="pf_phrases", height=260,
                             label_visibility="collapsed")
                st.button("Save list", on_click=_save_phrases)

    with right:
        with st.container(border=True, key="card_about"):
            st.subheader("About you", anchor=False)
            a, b = st.columns(2)
            a.text_input("Full name", key="pf_name", placeholder="Your name")
            b.text_input("Email", key="pf_email", placeholder="you@example.com")
            code, phone, city = st.columns([1, 2, 3])
            code.text_input("Country code", key="pf_country_code", placeholder="+1")
            phone.text_input("Phone", key="pf_phone", placeholder="(555) 555-0100")
            city.text_input("City", key="pf_city", placeholder="City, State")
            a, b = st.columns(2)
            a.text_input("LinkedIn", key="pf_linkedin", placeholder="https://www.linkedin.com/in/…")
            b.text_input("Portfolio or website", key="pf_portfolio", placeholder="https://")
            a, b = st.columns(2)
            a.selectbox("Default tone", profile_store.TONES, key="pf_tone")
            b.selectbox("Default length", profile_store.LENGTHS, key="pf_length")
            st.text_input("Sign-off", key="pf_sign_off")

        with st.container(border=True, key="card_mentions"):
            st.subheader("Always and never mention", anchor=False)
            st.caption(
                "Facts you want available for every letter, and things to leave out. "
                "Notes for a single job go on the New cover letter screen instead."
            )
            st.text_area(
                "Always mention (optional)",
                key="pf_always_mention",
                height=110,
                placeholder="For example: I'm open to relocating to Denver.",
            )
            st.text_area(
                "Never mention (optional)",
                key="pf_never_mention",
                height=110,
                placeholder="For example: don't mention my career break in 2022.",
            )

        _application_answers()
        _self_identification()
        _saved_answers()
        _watch_list()

        settings = config.load_settings()
        with st.container(border=True, key="card_settings"):
            a, b, c = st.columns(3)
            a.caption("Claude API key")
            a.markdown("**Set in .env**" if settings.key_status == "ok" else "**Not set**")
            b.caption("Adzuna API key")
            b.markdown("**Set in .env**" if settings.adzuna_status == "ok" else "**Not set**")
            c.caption("Model")
            c.markdown(f"`{settings.model}`")
