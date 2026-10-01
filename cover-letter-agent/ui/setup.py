"""Setup screen shown instead of the app when the API key is missing or malformed."""

import streamlit as st

import config


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
            """
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
