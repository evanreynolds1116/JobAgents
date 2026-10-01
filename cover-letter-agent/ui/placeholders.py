"""Screens that later phases fill in."""

import streamlit as st

from ui.style import coming_soon


def find_jobs_page() -> None:
    st.title("Find jobs")
    coming_soon("Job search", "Phase 3 (milestones 10 to 12)")
