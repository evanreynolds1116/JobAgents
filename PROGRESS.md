# PROGRESS.md: Job Application Assistant

This file tracks build progress against the spec ("Job Application Assistant — Build Spec").
**Claude: read this file at the start of every session and update it before the session ends.**

## How to use this file

- Work on one milestone at a time, in the build order below.
- Mark a milestone **Done** only when every acceptance criterion is checked off and the tests pass.
- Log decisions that differ from the spec in **Decisions & deviations**, with the reason. Ask the user before deviating.
- Add anything blocking progress to **Blockers & open questions**.
- Add one entry to the **Session log** per working session (newest first).

Status values: `Not started` · `In progress` · `Blocked` · `Done`

## Current status

- **Current milestone:** 2. Resume and profile
- **Next step:** User checks Milestone 1 (add a real key to `cover-letter-agent/.env`, run the app) and answers the open questions below; then build Milestone 2
- **Last updated:** 2026-10-01

## Build order

The cover letter agent comes first, then job search (Phase 3), then the application agent (Phase 2). Milestone numbers follow the spec.

| # | Milestone | Phase | Status |
|---|---|---|---|
| 1 | Skeleton and setup | 1. Cover letter | Done |
| 2 | Resume and profile | 1. Cover letter | Not started |
| 3 | Fetch and draft | 1. Cover letter | Not started |
| 4 | Verify, review and approve | 1. Cover letter | Not started |
| 5 | Export, history and evaluation | 1. Cover letter | Not started |
| 10 | Saved searches and Adzuna | 3. Job search | Not started |
| 11 | Filtering and fit scoring | 3. Job search | Not started |
| 12 | Hand-off and schedule | 3. Job search | Not started |
| 6 | Application profile | 2. Application | Not started |
| 7 | Greenhouse and Lever filler | 2. Application | Not started |
| 8 | General forms and answer learning | 2. Application | Not started |
| 9 | Multi-step platforms (stretch) | 2. Application | Not started |

## Acceptance criteria

### Phase 1: Cover letter agent

**Milestone 1. Skeleton and setup**
- [x] `streamlit run app.py` opens a page
- [x] A missing API key shows setup instructions instead of crashing
- [x] `data/`, `output/` and `.env` are gitignored

**Milestone 2. Resume and profile**
- [ ] Uploading the user's real resume (PDF or .docx) converts to `resume.md` with no missing sections
- [ ] Resume edits and profile fields (including writing sample) persist after a restart

**Milestone 3. Fetch and draft**
- [ ] URL input with the optional "Notes for this job" box
- [ ] Blocked or empty pages fall back to pasting the posting text
- [ ] 8 of the 10 test postings produce a draft with the correct company and title

**Milestone 4. Verify, review and approve**
- [ ] Humanize step and phrase linter run on every draft
- [ ] A deliberately inserted false claim gets flagged
- [ ] Export is unavailable until the letter is approved
- [ ] Editing after approval resets the status to `draft`

**Milestone 5. Export, history and evaluation**
- [ ] .docx and PDF export of approved letters
- [ ] Applications list with status, searchable by company or title
- [ ] Application detail page shows the saved job description (even after the original posting is gone), the letter version sent, key dates and a notes log
- [ ] All tests pass
- [ ] Quality evaluation (`scripts/eval.py`) meets the success criteria in the spec's Overview & goals

### Phase 3: Job search agent

**Milestone 10. Saved searches and Adzuna**
- [ ] A search for 2 titles × 2 cities over the last 3 days returns results with no duplicates
- [ ] Location rule: hybrid and on-site jobs outside the cities' radius are excluded; remote jobs from anywhere in the US are included (one nationwide remote query per title)
- [ ] Date-posted and salary filters work
- [ ] Adzuna usage is tracked and the app pauses before the daily limit (250 calls)

**Milestone 11. Filtering and fit scoring**
- [ ] On 20 hand-labeled postings, at least 17 get the right work setting
- [ ] The top-scored jobs match the user's own top picks

**Milestone 12. Hand-off and schedule**
- [ ] One click goes from a shortlisted job to a cover letter draft
- [ ] A scheduled run adds only new jobs
- [ ] Company watch list (Greenhouse, Lever, Ashby) works

### Phase 2: Application agent

**Milestone 6. Application profile**
- [ ] Every standard-answer field can be entered, edited and persists
- [ ] Saved answers to past questions are stored and reusable

**Milestone 7. Greenhouse and Lever filler**
- [ ] On 5 real Greenhouse or Lever postings, at least 90% of non-sensitive fields are filled correctly
- [ ] The agent reaches the right form from Adzuna links and pasted links
- [ ] The agent never submits (code-level block verified by test)
- [ ] Every field's final value, including the user's edits, is saved to the application's record and shown on its detail page

**Milestone 8. General forms and answer learning**
- [ ] On 5 postings from other platforms, every required field is filled or clearly flagged
- [ ] Fill without cover letter works, and pauses when a form requires a cover letter

**Milestone 9. Multi-step platforms (stretch)**
- [ ] A full Workday application reaches the final review page, with the user handling the login

## Decisions & deviations

| Date | Decision | Reason | Approved by user? |
|---|---|---|---|
| 2026-10-01 | App code lives in `cover-letter-agent/` (the spec's project layout), next to the planning docs. Run it from that folder | Follows the spec layout; Streamlit reads `.streamlit/config.toml` from the working folder | n/a (per spec) |
| 2026-10-01 | Storage uses stdlib `sqlite3`, not SQLModel | Spec allows either; no extra dependency | n/a (spec option) |
| 2026-10-01 | Added `config.py` (not in the spec's layout) to load `.env` and hold folder paths | Shared by the UI, storage and tests; keeps `app.py` UI-only | Yes |
| 2026-10-01 | API key check at start-up is local only: missing, or not starting with `sk-ant-`, shows setup instructions. A revoked or wrong-but-well-formed key is caught on the first API call (Milestone 3) | Avoids a network call on every page load | Yes |
| 2026-10-01 | `.env` is re-read on every page load, so the setup screen's "Check again" works without a restart. The key is read from `.env` only, not from shell environment variables | Spec: configuration lives in `.env` | n/a |
| 2026-10-01 | Mockup fonts (Public Sans, IBM Plex Mono 400/500, Source Serif 4) bundled in `cover-letter-agent/static/fonts/` with their OFL licenses, served by Streamlit's static serving. Source Serif 4 is declared for the letter text (review screen, Milestone 4). Source Serif 4 italic left out to save ~0.9 MB | Loading from Google Fonts at run time would be a third-party request, which the spec rules out | Yes |
| 2026-10-01 | Streamlit usage statistics turned off (`gatherUsageStats = false`) and the server bound to `localhost` | Spec: no analytics or third-party services; local-only app | n/a (per spec) |
| 2026-10-01 | `requirements.txt` lists only what Milestone 1 uses; later milestones add their own libraries | Smaller install until they're needed | n/a |
| 2026-10-01 | Job notes log (`applications.notes`) stored as a JSON list of `{date, text}` entries | Spec says "dated entries" without a format | n/a |

## Blockers & open questions

- [ ] Confirm the defaults listed in the spec's "Open questions & defaults assumed" table with the user
- [ ] Get a writing sample (for example, a past cover letter) from the user for the profile
- [ ] User to create API keys: Anthropic (needed from milestone 1), Adzuna (needed from milestone 10)
- [x] Fonts: bundle locally (approved 2026-10-01)
- [x] Approve or change the "Pending" rows in Decisions & deviations (all approved 2026-10-01)
- [x] Git repository initialized at the workspace root (2026-10-01); nothing committed yet

## Session log

### 2026-10-01
- Worked on: Milestone 1, skeleton and setup
- Completed: `cover-letter-agent/` with the spec's layout (`app.py`, `agent/` with `fetch.py`, `pipeline.py`, `prompts/`, `style/banned_phrases.txt` with the 10 starting phrases, `storage/db.py`, `export/docx.py`, `data/`, `output/`, `tests/fixtures/`), plus `config.py`, `.env.example`, `.gitignore`, `requirements.txt`, `README.md` and `.streamlit/config.toml` (mockup colors, 44 px controls). SQLite schema for `applications` and `drafts` matching the spec's columns, with a status check and one row per draft version. Streamlit app with the mockup's sidebar (Find jobs, New cover letter, Applications, Profile & resume) and placeholder pages; a missing or malformed key shows a setup screen with a "Check again" button. Virtualenv at `cover-letter-agent/.venv`. Launch config for the Claude app's preview pane at `.claude/launch.json`.
- Tests: 22 passed (`pytest`): settings and key status, schema columns and constraints, gitignore rules (checked with `git check-ignore`), and app start-up via Streamlit's AppTest (missing key, malformed key, "Check again" picking up a new key, normal start creating `data/app.db`). Also ran `streamlit run app.py` and checked the setup screen and all four pages in a browser; no server errors.
- Follow-up (same day): user approved the three pending decisions. Bundled the mockup fonts locally (downloaded once from github.com/google/fonts) and checked in the browser that they load from localhost with no requests to Google. Added `tests/test_theme.py`. Ran `git init` at the workspace root; `.env`, `data/`, `output/` and `.venv/` confirmed ignored. Tests: 24 passed.
- Next: Milestone 2 (resume upload and conversion, profile form, persistence)

<!-- Newest first. One entry per session:
### YYYY-MM-DD
- Worked on:
- Completed:
- Tests:
- Next:
-->
