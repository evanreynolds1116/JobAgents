"""Job Application Assistant: Streamlit UI.

Run with:  streamlit run app.py
Built so far: navigation and start-up checks (Milestone 1), Profile & resume (Milestone 2).
"""

import streamlit as st

import config
from storage import db, profile as profile_store, resume

st.set_page_config(page_title="Job Assistant", page_icon="✉️", layout="wide")

# Design tokens from ui-mockup/README.md. Streamlit's theme (.streamlit/config.toml)
# covers colors; this covers the sizes the theme can't set.
st.html(
    """
<style>
h1 { font-size: 32px !important; font-weight: 700 !important; letter-spacing: -0.01em; }
.stButton button, .stFormSubmitButton button, .stDownloadButton button { min-height: 44px; }
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] { min-height: 44px; }
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p { font-size: 15px; }
[class*="st-key-card_"] { background: #FFFFFF; border-radius: 12px; padding: 24px; }
[data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"],
[data-testid="stSelectbox"] div:has(> input) { border-color: #C5CDD5; }
[data-testid="stTextInputRootElement"] { min-height: 44px; }
.ja-brand { color: #FFFFFF; font-weight: 700; font-size: 18px; margin: 0; }
.ja-tagline { color: #A9B6C2; font-size: 13px; margin: 0 0 12px; }
.ja-footnote { color: #A9B6C2; font-size: 13px; line-height: 1.5; margin-top: 24px; }
.ja-muted { color: #4F5B66; }
.ja-file { font-family: 'IBM Plex Mono', monospace; font-size: 14px; }
.st-key-pf_resume_text textarea { font-family: 'IBM Plex Mono', monospace; font-size: 13px; line-height: 1.6; }
</style>
"""
)


@st.cache_resource
def _startup() -> bool:
    """Create data/, output/ and the database once per server process."""
    config.ensure_dirs()
    db.init_db()
    return True


# --- Pages -----------------------------------------------------------------


def coming_soon(what: str, milestone: str) -> None:
    with st.container(border=True, key="card_coming_soon"):
        st.markdown(f"**{what}** arrives in {milestone}.")
        st.caption("This page is a placeholder in the Milestone 1 skeleton.")


def find_jobs_page() -> None:
    st.title("Find jobs")
    coming_soon("Job search", "Phase 3 (milestones 10 to 12)")


def new_letter_page() -> None:
    st.title("New cover letter")
    coming_soon("Job link, notes for this job and Generate draft", "Milestone 3")


def applications_page() -> None:
    st.title("Applications")
    coming_soon("The applications list with search and status", "Milestone 5")


# Profile & resume -----------------------------------------------------------

PROFILE_FIELDS = ("name", "email", "phone", "city", "link", "tone", "length",
                  "sign_off", "always_mention", "never_mention")


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
        st.markdown(
            '<p class="ja-muted">Used by all three agents. Stored only on this computer.</p>',
            unsafe_allow_html=True,
        )
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

    with right:
        with st.container(border=True, key="card_about"):
            st.subheader("About you", anchor=False)
            a, b = st.columns(2)
            a.text_input("Full name", key="pf_name", placeholder="Your name")
            b.text_input("Email", key="pf_email", placeholder="you@example.com")
            a.text_input("Phone", key="pf_phone", placeholder="(555) 555-0100")
            b.text_input("City", key="pf_city", placeholder="City, State")
            st.text_input("LinkedIn or portfolio", key="pf_link", placeholder="https://")
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
            a, b = st.columns(2)
            a.caption("Claude API key")
            a.markdown("**Set in .env**" if settings.key_status == "ok" else "**Not set**")
            b.caption("Model")
            b.markdown(f"`{settings.model}`")


# --- Setup screen (missing or invalid API key) ------------------------------


def setup_page(settings: config.Settings) -> None:
    st.title("Connect your Claude API key")
    if settings.key_status == "missing":
        st.warning("No Claude API key was found in `.env`, so drafting can't run yet.")
    else:
        st.error(
            "The key in `.env` doesn't look like a Claude API key. "
            f"Claude keys start with `{config.KEY_PREFIX}`."
        )

    with st.container(border=True, key="card_setup"):
        st.markdown(
            f"""
1. Create a key at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys).
2. In the app folder, copy `.env.example` to a new file named `.env`.
3. Paste your key after `ANTHROPIC_API_KEY=` and save the file.
4. Click **Check again**. You don't need to restart the app.
"""
        )
        st.caption("Your `.env` file goes here:")
        st.code(str(config.ENV_PATH), language=None)
        st.caption(
            "The key stays on this computer. `.env` is gitignored and the key is never logged."
        )
        if st.button("Check again", type="primary"):
            st.rerun()


# --- Layout ----------------------------------------------------------------


def sidebar(pages: list) -> None:
    with st.sidebar:
        st.markdown(
            '<p class="ja-brand">Job Assistant</p><p class="ja-tagline">Runs on your computer</p>',
            unsafe_allow_html=True,
        )
        for page in pages:
            st.page_link(page)
        st.markdown(
            '<p class="ja-footnote">Nothing is sent or submitted without you.</p>',
            unsafe_allow_html=True,
        )


def main() -> None:
    _startup()
    settings = config.load_settings()

    if settings.key_status != "ok":
        with st.sidebar:
            st.markdown(
                '<p class="ja-brand">Job Assistant</p><p class="ja-tagline">Runs on your computer</p>',
                unsafe_allow_html=True,
            )
        setup_page(settings)
        return

    pages = [
        st.Page(find_jobs_page, title="Find jobs", url_path="find-jobs"),
        st.Page(new_letter_page, title="New cover letter", url_path="new-letter", default=True),
        st.Page(applications_page, title="Applications", url_path="applications"),
        st.Page(profile_page, title="Profile & resume", url_path="profile"),
    ]
    current = st.navigation(pages, position="hidden")
    sidebar(pages)
    current.run()


if __name__ == "__main__":  # Streamlit runs this file as __main__; tests import it
    main()
