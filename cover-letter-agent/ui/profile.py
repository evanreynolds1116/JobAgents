"""Profile & resume screen (Milestone 2)."""

import streamlit as st

import config
from agent import lint
from storage import profile as profile_store
from storage import resume
from ui.style import muted

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


def _profile_from_state() -> profile_store.Profile:
    values = {name: st.session_state.get(f"pf_{name}", "") for name in PROFILE_FIELDS}
    values["country_code"] = profile_store.normalize_country_code(values["country_code"])
    samples = [st.session_state.get(f"pf_sample_{i}", "")
               for i in range(st.session_state.get("pf_sample_count", 1))]
    return profile_store.Profile(**values, writing_samples=[s for s in samples if s.strip()])


def _has_unsaved_changes() -> bool:
    if _profile_from_state() != profile_store.load():
        return True
    return st.session_state.get("pf_resume_text", "").strip() != resume.load_text().strip()


def _save_profile() -> None:
    current = _profile_from_state()
    profile_store.save(current)
    st.session_state.pf_country_code = current.country_code  # show "+44", not "44"
    resume.save_text(st.session_state.get("pf_resume_text", ""))
    st.session_state.pf_flash = ("success", "Saved.")
    st.session_state.pf_problems = current.problems()


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

        settings = config.load_settings()
        with st.container(border=True, key="card_settings"):
            a, b, c = st.columns(3)
            a.caption("Claude API key")
            a.markdown("**Set in .env**" if settings.key_status == "ok" else "**Not set**")
            b.caption("Adzuna API key")
            b.markdown("**Set in .env**" if settings.adzuna_status == "ok" else "**Not set**")
            c.caption("Model")
            c.markdown(f"`{settings.model}`")
