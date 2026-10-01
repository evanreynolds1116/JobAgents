# Job Application Assistant

A local Streamlit app that drafts cover letters with the Claude API. See `../SPEC.md` for the full spec and `../PROGRESS.md` for build status.

## Setup (Windows)

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Then paste your Claude API key into `.env` after `ANTHROPIC_API_KEY=`.

## Layout

- `app.py` runs start-up checks and navigation; each screen is in `ui/`.
- `agent/fetch.py` reads job postings; `agent/pipeline.py` runs the Claude steps; prompts are in `agent/prompts/`.
- `storage/` holds the database, resume and profile code. Your data lives in `data/` (gitignored).

## Run

From this folder (so Streamlit picks up `.streamlit/config.toml`):

```
.venv\Scripts\streamlit run app.py
```

It opens at http://localhost:8501. Without a valid key the app shows setup instructions instead of the main screens.

## Export

Approve a letter on the review screen, then use **Export .docx** or **Export PDF**. Files are saved in `output/` as `Company - Title - Cover Letter.docx` / `.pdf`. PDF export uses Microsoft Word through `docx2pdf` (or LibreOffice if it's installed instead).

## Quality evaluation

Save postings as `tests/fixtures/real/NN.txt` and list them in `tests/fixtures/real/postings.json` (expected company and title, optional notes, whether your resume is a weak match). Then:

```
.venv\Scripts\python scripts\eval.py
```

It runs every posting through all five steps (it asks first, since it costs a few cents each) and writes `report.md`, one letter per posting and `scores.csv` for your own scores to `output/eval/<date-time>/`. Both folders are gitignored.

## Test

Tests never call the Claude API. Everything committed in `tests/fixtures/` is made up (your real postings in `tests/fixtures/real/` stay out of git): resume PDFs (regenerate with `make_resume_fixtures.py`), job postings in `postings/`, and real Claude responses for those postings in `recorded/`. After changing a prompt or schema, re-record them with your key (costs a few cents):

```
.venv\Scripts\python tests\fixtures\record_pipeline.py
```

Run the tests:

```
.venv\Scripts\python -m pytest
```
