"""Job Application Assistant: Streamlit UI.

Run with:  streamlit run app.py
Milestone 1 is the skeleton: navigation, start-up checks and placeholder pages.
"""

import streamlit as st

import config
from storage import db

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
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
.ja-brand { color: #FFFFFF; font-weight: 700; font-size: 18px; margin: 0; }
.ja-tagline { color: #A9B6C2; font-size: 13px; margin: 0 0 12px; }
.ja-footnote { color: #A9B6C2; font-size: 13px; line-height: 1.5; margin-top: 24px; }
.ja-muted { color: #4F5B66; }
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
    with st.container(border=True):
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


def profile_page() -> None:
    st.title("Profile & resume")
    st.markdown(
        '<p class="ja-muted">Used by all three agents. Stored only on this computer.</p>',
        unsafe_allow_html=True,
    )
    coming_soon("Resume upload, profile and writing sample", "Milestone 2")
    settings = config.load_settings()
    with st.container(border=True):
        left, right = st.columns(2)
        left.caption("Claude API key")
        left.markdown("**Set in .env**" if settings.key_status == "ok" else "**Not set**")
        right.caption("Model")
        right.markdown(f"`{settings.model}`")


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

    with st.container(border=True):
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


main()
