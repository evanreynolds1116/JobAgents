"""Shared styling and small layout pieces.

Design tokens come from ui-mockup/README.md. Streamlit's theme (.streamlit/config.toml)
covers colors and fonts; this CSS covers the sizes and details the theme can't set.
"""

import streamlit as st

CSS = """
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
.ja-crumb { color: #4F5B66; font-size: 14px; margin: 0; }
.ja-file { font-family: 'IBM Plex Mono', monospace; font-size: 14px; }
.st-key-pf_resume_text textarea { font-family: 'IBM Plex Mono', monospace; font-size: 13px; line-height: 1.6; }
.st-key-nl_url input { font-family: 'IBM Plex Mono', monospace; font-size: 14px; }
.ja-letter p { font-family: 'Source Serif 4', Georgia, serif; font-size: 17px; line-height: 1.6; margin: 0 0 14px; }
.ja-letter mark { padding: 1px 2px; border-radius: 3px; cursor: help; color: inherit; }
mark.ja-flag-claim { background: #FBE9E7; border-bottom: 2px solid #A3261C; }
mark.ja-flag-style { background: #FDF1E2; border-bottom: 2px solid #8A4B08; }
[class*="st-key-ap_open_"] button { min-height: 28px; padding: 0; justify-content: flex-start; }
[class*="st-key-ap_open_"] button p { font-size: 15px; font-weight: 600; text-align: left; }
.st-key-card_posting h1, .st-key-card_posting h2, .st-key-card_posting h3 {
  font-size: 17px !important; font-weight: 700 !important; padding: 8px 0 4px !important;
}
.ja-strength { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 13px; font-weight: 600; }
.ja-strong { background: #E3F1EE; color: #0B4F47; }
.ja-partial { background: #FDF1E2; color: #8A4B08; }
.ja-none { background: #FBE9E7; color: #A3261C; }
</style>
"""


def inject() -> None:
    st.html(CSS)


def brand() -> None:
    st.markdown(
        '<p class="ja-brand">Job Assistant</p><p class="ja-tagline">Runs on your computer</p>',
        unsafe_allow_html=True,
    )


def footnote() -> None:
    st.markdown(
        '<p class="ja-footnote">Nothing is sent or submitted without you.</p>',
        unsafe_allow_html=True,
    )


def muted(text: str) -> None:
    st.markdown(f'<p class="ja-muted">{text}</p>', unsafe_allow_html=True)
