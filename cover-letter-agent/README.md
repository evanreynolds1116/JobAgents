# Job Application Assistant

A local Streamlit app that drafts cover letters with the Claude API. See `../SPEC.md` for the full spec and `../PROGRESS.md` for build status.

## Setup (Windows)

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Then paste your Claude API key into `.env` after `ANTHROPIC_API_KEY=`.

## Run

From this folder (so Streamlit picks up `.streamlit/config.toml`):

```
.venv\Scripts\streamlit run app.py
```

It opens at http://localhost:8501. Without a valid key the app shows setup instructions instead of the main screens.

## Test

```
.venv\Scripts\python -m pytest
```
