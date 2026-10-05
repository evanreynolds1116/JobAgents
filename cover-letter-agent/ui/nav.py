"""Page registry and navigation between screens.

Pages are functions, so switching to one needs an st.Page built the same way as in
st.navigation. `page(key)` builds it; `go(key, ...)` switches to it.
"""

import streamlit as st

# key: (title, url path, shown in the sidebar)
PAGES = {
    "find_jobs": ("Find jobs", "find-jobs", True),
    "new_letter": ("New cover letter", "new-letter", True),
    "applications": ("Applications", "applications", True),
    "profile": ("Profile & resume", "profile", True),
    "review": ("Review and approve", "review", False),
    "detail": ("Application details", "application", False),
}
DEFAULT = "new_letter"


def _page_function(key: str):
    from ui import applications, detail, find_jobs, new_letter, profile, review

    return {
        "find_jobs": find_jobs.find_jobs_page,
        "new_letter": new_letter.new_letter_page,
        "applications": applications.applications_page,
        "profile": profile.profile_page,
        "review": review.review_page,
        "detail": detail.detail_page,
    }[key]


def page(key: str) -> st.Page:
    title, url_path, _ = PAGES[key]
    return st.Page(_page_function(key), title=title, url_path=url_path, default=key == DEFAULT)


def all_pages() -> list[st.Page]:
    return [page(key) for key in PAGES]


def sidebar_pages() -> list[st.Page]:
    return [page(key) for key, (_, _, shown) in PAGES.items() if shown]


def go(key: str, **query_params) -> None:
    st.switch_page(page(key), query_params=query_params or None)
