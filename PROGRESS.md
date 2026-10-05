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

- **Current milestone:** 7. Greenhouse and Lever filler (built; live check on 5 real postings needs you); 11 is waiting on your labels, 5 on your scores
- **Next step:** Fill in your application answers on Profile & resume, then pick 5 real Greenhouse or Lever postings for the Milestone 7 live check (see Blockers); separately, label the Milestone 11 sheet and score the Milestone 5 evaluation
- **Last updated:** 2026-10-05

## Build order

The cover letter agent comes first, then job search (Phase 3), then the application agent (Phase 2). Milestone numbers follow the spec.

| # | Milestone | Phase | Status |
|---|---|---|---|
| 1 | Skeleton and setup | 1. Cover letter | Done |
| 2 | Resume and profile | 1. Cover letter | Done |
| 3 | Fetch and draft | 1. Cover letter | Done |
| 4 | Verify, review and approve | 1. Cover letter | Done |
| 5 | Export, history and evaluation | 1. Cover letter | In progress (awaiting the quality evaluation) |
| 10 | Saved searches and Adzuna | 3. Job search | Done (2026-10-05) |
| 11 | Filtering and fit scoring | 3. Job search | In progress (live run done; waiting on your labels) |
| 12 | Hand-off and schedule | 3. Job search | Done (2026-10-05) |
| 6 | Application profile | 2. Application | Done (2026-10-05) |
| 7 | Greenhouse and Lever filler | 2. Application | In progress (built and tested; live check on 5 real postings pending) |
| 8 | General forms and answer learning | 2. Application | Not started |
| 9 | Multi-step platforms (stretch) | 2. Application | Not started |

## Acceptance criteria

### Phase 1: Cover letter agent

**Milestone 1. Skeleton and setup**
- [x] `streamlit run app.py` opens a page
- [x] A missing API key shows setup instructions instead of crashing
- [x] `data/`, `output/` and `.env` are gitignored

**Milestone 2. Resume and profile**
- [x] Uploading the user's real resume (PDF or .docx) converts to `resume.md` with no missing sections (confirmed by user 2026-10-01)
- [x] Resume edits and profile fields (including writing sample) persist after a restart

**Milestone 3. Fetch and draft**
- [x] URL input with the optional "Notes for this job" box
- [x] Blocked or empty pages fall back to pasting the posting text (login walls, JavaScript shells, 403/404, LinkedIn/Indeed; covered by tests)
- [x] 8 of the 10 test postings produce a draft with the correct company and title (8 of 8 real postings correct; the 2 LinkedIn postings need pasted text)

**Milestone 4. Verify, review and approve**
- [x] Humanize step and phrase linter run on every draft
- [x] A deliberately inserted false claim gets flagged (live verifier run on a letter with an invented Google job, replayed in `test_deliberately_inserted_false_claim_is_flagged`)
- [x] Export is unavailable until the letter is approved (buttons disabled, `require_approved` refuses drafts)
- [x] Editing after approval resets the status to `draft`

**Milestone 5. Export, history and evaluation**
- [x] .docx and PDF export of approved letters (PDF checked with Microsoft Word)
- [x] Applications list with status, searchable by company or title
- [x] Application detail page shows the saved job description (even after the original posting is gone), the letter version sent, key dates and a notes log
- [x] All tests pass (187 passed, 1 skipped: the real Word conversion, run on demand with `JOBAGENTS_PDF_TEST=1`)
- [ ] Quality evaluation (`scripts/eval.py`) meets the success criteria in the spec's Overview & goals (latest letter for each of the 10 postings: 10 of 10 correct company and title, 10 of 10 with zero unsupported claims, 10 of 10 with no banned phrases, 10 of 10 within 250–400 words; waiting on your scores)

### Phase 3: Job search agent

**Milestone 10. Saved searches and Adzuna**
- [x] A search for 2 titles × 2 cities over the last 3 days returns results with no duplicates (live run 2026-10-05: 43 jobs stored, 0 duplicates, 12 cross-query repeats merged)
- [x] Location rule: hybrid and on-site jobs outside the cities' radius are excluded; remote jobs from anywhere in the US are included (one nationwide remote query per title) (live 2026-10-05: 69 non-remote nationwide results dropped; city results are now checked against the job's coordinates, which dropped a Morristown, TN job 39.7 mi from Knoxville that Adzuna's 25 mi filter let through)
- [x] Date-posted and salary filters work (live 2026-10-05: none of the stored jobs was older than 3 days; with a $90k minimum, the app checks stated salaries only; two Vontier jobs with only Adzuna estimates of $71k and $75k are kept and labeled "est.")
- [x] Adzuna usage is tracked and the app pauses before the daily limit (250 calls)

**Milestone 11. Filtering and fit scoring**
- [ ] On 20 hand-labeled postings, at least 17 get the right work setting (sheet written 2026-10-05: `output/job_labels/2026-10-05_120937/labels.csv`; 9 of its 20 are "unknown", see Blockers)
- [ ] The top-scored jobs match the user's own top picks (same sheet: mark your top 5)
- [x] Salary and work-setting filters run on Claude's labels; jobs with no fit score are kept and shown last (tests)

**Milestone 12. Hand-off and schedule**
- [x] One click goes from a shortlisted job to a cover letter draft (live 2026-10-05: Start letter on OnePay "Software Engineer, Risk" from the watch list went straight to the review screen with a checked 350-word draft in about 2.5 minutes; Adzuna jobs open New cover letter ready to paste, since Adzuna blocks automated reading)
- [x] A scheduled run adds only new jobs (tests: a second scheduled run adds 0 new jobs; the live scheduled-run check was skipped by your choice)
- [x] Company watch list (Greenhouse, Lever, Ashby) works (all three APIs read live on 5 real boards; OnePay and Realm added in the app and run live: 9 jobs stored and scored)

### Phase 2: Application agent

**Milestone 6. Application profile**
- [x] Every standard-answer field can be entered, edited and persists (work authorization, sponsorship, relocation, start date, how you hear about jobs, plus salary and address; tested by entering, saving, reopening and editing; checked in the running app)
- [x] Saved answers to past questions are stored and reusable (add, edit, delete on Profile & resume; `find_similar` finds the closest saved question for Milestone 8, and `record_use` counts reuse)

**Milestone 7. Greenhouse and Lever filler**
- [ ] On 5 real Greenhouse or Lever postings, at least 90% of non-sensitive fields are filled correctly (needs your application answers and 5 postings; field reading checked read-only on a real Greenhouse and a real Lever form, all labels correct)
- [ ] The agent reaches the right form from Adzuna links and pasted links (pasted links: tests and a real Ashby link; Adzuna: works in tests, but the real Adzuna site answers the app's browser with HTTP 403 "Access Denied", so the agent stops and asks for the company's link; see Decisions)
- [x] The agent never submits (code-level block verified by test: every click goes through `guard.safe_click`, which refuses submit-type controls and Submit/Apply/Send/Accept buttons; tested on Greenhouse- and Lever-shaped forms, a cookie banner and a decoy Apply button)
- [x] Every field's final value, including the user's edits, is saved to the application's record and shown on its detail page (`filled_answers`; detail page "Your answers" tab; values that differ from what the agent entered are recorded as yours)

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
| 2026-10-01 | Resume conversion uses `pdfplumber` (PDF) and `python-docx` (.docx), both MIT-licensed | Spec doesn't name libraries; `python-docx` is already planned for export | n/a |
| 2026-10-01 | Added `storage/resume.py` (convert, store, hash) and `storage/profile.py` (`profile.yaml`), which aren't in the spec's layout | Keeps file storage next to `storage/db.py`; same reasoning as `config.py` | Yes |
| 2026-10-01 | Writing sample built in Milestone 2, not 4, and supports several samples ("Add another sample") | PROGRESS.md lists it under Milestone 2; spec's profile allows "one or more samples" | n/a |
| 2026-10-01 | Uploading converts right away and saves both the original and `resume.md`. Replacing a resume warns first that it overwrites edited text | Fewer steps; the original is never lost | n/a |
| 2026-10-01 | Profile also holds a default length (250–400 words or under 250) next to tone | Spec's profile lists "target length"; options match the New cover letter mockup | n/a |
| 2026-10-01 | `app.py` only calls `main()` when Streamlit runs it, so tests can import it and render one page | Streamlit's test tool can only switch between file-based pages | n/a |
| 2026-10-01 | Each screen will move to its own file under `ui/`; `app.py` keeps start-up checks and navigation | `app.py` would grow too large by Milestone 4 | Yes |
| 2026-10-01 | Profile has a phone country code (default +1, before Phone) and separate LinkedIn and portfolio links, instead of the spec's single "LinkedIn or portfolio URL". A saved `link` is moved to the matching field on load | User request | Yes (user's request) |
| 2026-10-01 | All pipeline steps use `claude-opus-5-5` instead of the spec's `claude-sonnet-5-5` (still set in `.env`) | User request | Yes (user's request) |
| 2026-10-01 | Server-side refusal fallback turned on (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`): if Claude declines a step, the API retries it on a fallback model in the same call | Anthropic's recommended default for this model; a refusal on a cover letter is very unlikely | Yes |
| 2026-10-01 | Effort per step: parse `low`, match `low`, draft `medium`. Match was `medium` until real postings took 44–66 seconds; at `low` the slowest one took 45 seconds | Spec goal: first draft in under a minute | Yes (user chose `low` for match) |
| 2026-10-01 | The fetcher doesn't request LinkedIn, Indeed, Glassdoor, Jobright or HiringCafe pages at all and goes straight to the paste box. It identifies itself honestly instead of imitating a browser | Their terms forbid automated reading (spec, Phase 3 guardrails); same outcome as the spec's paste fallback | Yes |
| 2026-10-01 | The fetcher prefers a page's embedded schema.org JobPosting data when present, and caps posting text at 30,000 characters with a warning | Structured data survives JavaScript-heavy pages and gives the exact company and title; the cap is the spec's "very long posting" rule | n/a |
| 2026-10-01 | Parse output adds `several_jobs`; match output gives each requirement a `kind`, a `feature` flag and evidence as `{quote, source}`. Code drops any quote that isn't really in the resume or notes, and keeps at most 4 featured | `several_jobs` drives the spec's confirm-company-and-title case; the quote check stops invented evidence before drafting | n/a |
| 2026-10-01 | The draft step returns `{"letter": ...}` through structured outputs rather than free text, and gets the banned-phrase list to avoid. The phrase linter itself comes in Milestone 4 | No stray preamble around the letter; fewer phrases for step 4 to fix | n/a |
| 2026-10-01 | Tone and length are chosen per letter on the New cover letter screen (defaulting to the profile) and aren't stored with the draft | The spec's `drafts` table has no column for them | n/a |
| 2026-10-01 | Same-URL detection ignores tracking parameters (`utm_*`, `gh_src`, etc.), fragments and trailing slashes | So a link shared from a different place still finds the existing application | n/a |
| 2026-10-01 | Milestone 3 includes a basic review screen (posting summary, match, draft, versions, copy). Approve, editing, claim checks and revise-with-feedback are Milestone 4 | Somewhere to see the draft after Generate | n/a |
| 2026-10-01 | Pipeline tests replay real Claude responses recorded for made-up postings (`tests/fixtures/recorded/`, re-recorded with `tests/fixtures/record_pipeline.py`) | Spec: tests use recorded API responses so they cost nothing | n/a |
| 2026-10-01 | The 10 real acceptance postings go in `tests/fixtures/real/`, which is gitignored; made-up fixtures stay in git | The repo is public and real postings are other companies' text | Yes |
| 2026-10-01 | Linter lives in `agent/lint.py`: the banned-phrase list (case-insensitive, also catching forms like "leveraged"), more than one em dash, and "I am writing to express my interest"-style openers | Spec's phrase linter and style rules | n/a |
| 2026-10-01 | Verify step may also cite the `posting` as a source, for claims about the company or role | The spec's sources (resume, profile, notes) cover the candidate; company facts should still trace to something | n/a |
| 2026-10-01 | Code double-checks the verifier: a claim marked supported whose quote isn't in that source is flagged instead. Quotes (here and in matching) are compared on letters and digits only | Catches invented support; the letters-and-digits comparison stops PDF line breaks ("sealed-" / "bid") causing false flags | n/a |
| 2026-10-01 | Approve stays locked while anything is flagged (unsupported claims, style flags, leftover linter hits, or an unchecked version) until you tick "I've reviewed the flagged items" | Spec requires this for unsupported claims; the mockup's review panel covers style items too | n/a |
| 2026-10-01 | Your own edits are checked (verify) but not reworded (no humanize). "Ask for changes" reruns steps 3 to 5. "It's true: add to notes" adds the claim to the job notes and re-checks; "Remove sentence" saves a new version without it; "Rewrite this sentence" is "Ask for changes" with the flag as feedback | Spec's review screen and the mockup's actions | n/a |
| 2026-10-01 | Approving records `approved_at` and `sent_version` (the version you approved). Any new version (edit, redraft, restore) returns the letter to draft and clears both | Spec: approval gate, and "the exact cover letter version you sent" | n/a |
| 2026-10-01 | Export buttons are shown but disabled; they stay disabled after approval until Milestone 5 builds the exporter | Milestone 4 acceptance covers the gate only | n/a |
| 2026-10-01 | The banned-phrase list can be edited from Profile & resume ("Edit list"). It's saved to `agent/style/banned_phrases.txt`, which is tracked in git | Mockup shows "Banned phrases: 10 · Edit list" | n/a |
| 2026-10-01 | Effort: humanize `low`, verify `medium`. All five steps took 85 seconds on a real posting (verify 30 s) | Verify is the safety check, so it gets more effort; user chose to keep verify at `medium` over saving ~15 seconds | Yes |
| 2026-10-01 | Export template: your name (bold), a contact line (city, email, phone, LinkedIn, portfolio), the date, then the letter; Calibri 11 pt, 1-inch margins. Always exports the version you approved, even if newer drafts exist | Spec default: "a simple template with your name and contact details at the top" | n/a |
| 2026-10-01 | PDF export runs docx2pdf (Microsoft Word) in a separate process with a 2-minute limit, then LibreOffice if installed. If neither works, the .docx is still saved and you're told why | Spec: "PDF via docx2pdf or LibreOffice"; a separate process keeps Word's automation off Streamlit's threads | n/a |
| 2026-10-01 | Exports are saved to `output/` and offered as a download button. Submitted letters can still be exported | Spec: exported letters live in `output/` | n/a |
| 2026-10-01 | Application detail adds "Mark as submitted" (records `submitted_at`), Archive and Restore. Restore returns to submitted, approved or draft based on the dates on record | Spec's lookup needs "the dates you ... applied", and the app never submits anything itself | n/a |
| 2026-10-01 | "Your answers" tab on the detail page is a placeholder until Phase 2 | Filled answers come from the application agent | n/a |
| 2026-10-01 | `scripts/eval.py` reads a manifest (`tests/fixtures/real/postings.json`, gitignored) with expected company and title, optional notes and a weak-match flag; asks before spending money unless `--yes`; writes `report.md`, per-posting letters and verifier reports, and `scores.csv` for the judgment calls to `output/eval/<date-time>/` | Spec: run all 10, save drafts and verifier reports side by side; the manifest makes results comparable run to run | n/a |
| 2026-10-01 | Automatic fix-up pass after step 5: if verify flags unsupported claims, one call (`agent/prompts/fix_claims.md`, effort `low`) rewrites each to say only what the sources support or removes it, leaving everything else word for word; then verify runs again. At most once per draft, and never on your own edits. Anything still unsupported stays flagged for review | First evaluation: 5 of 6 letters had small embellishments, against the spec's goal of zero unsupported claims. Adds about 30–40 seconds to letters that need it | Yes (user chose option a) |
| 2026-10-01 | Job search code lives in a new `search/` package (`criteria.py`, `adzuna.py`, `normalize.py`, `run.py`) with storage in `storage/jobs.py`; tables `saved_searches`, `jobs` and `api_usage` | Spec names the tables but no folder for Phase 3 code (Phase 2 gets `apply/`) | n/a |
| 2026-10-01 | Adzuna queries use `title_only=<title>` (so results have the title in their title) with `where` + `distance` (miles converted to km) for each city, and `title_only=<title>` + `what=remote` with no location for the nationwide remote query. One page of 50 results per query, sorted by date, `max_days_old` 1/3/7. The salary range is no longer sent (see 2026-10-05) | Parameter names checked against Adzuna's published API spec; matches the spec's query plan and sizing (3 titles × 3 = 9 calls) | n/a |
| 2026-10-01 | Until Milestone 11 adds Claude's classification, the work setting is read from the posting text (hybrid / remote / on-site keywords, else Unknown). City-query results that aren't remote are also checked against the job's coordinates (see 2026-10-05); nationwide results are kept only if labeled remote | Spec's location rule; the city check needs no geocoding service | n/a |
| 2026-10-01 | Duplicate key: company (minus Inc., LLC and similar), title and city, lowercased with punctuation removed; remote jobs use "remote" as the place. A repeat from the same source ID also counts as seen. Known jobs keep their status (a dismissed job isn't shown as new again) | Spec: same company, title and location becomes one record; seen jobs aren't new again | n/a |
| 2026-10-01 | Adzuna allowance: the run is refused before any call if it would pass 250 calls today or 2,500 this month. Calls are counted per day, including failed ones. A failed query is reported and the rest still run | Spec: track usage and pause before the daily limit | n/a |
| 2026-10-05 | City results are checked again by distance: the job's latitude and longitude (sent by Adzuna) against the city's, great-circle miles, with no tolerance; jobs over the radius are dropped. Remote jobs aren't checked. Jobs without coordinates are left to Adzuna's filter. City coordinates come from `search/us_places.csv` (32,147 places), built by `scripts/build_places.py` from the Census Bureau's 2025 Gazetteer place file (public domain). Cities must be typed as city, state ("Nashville, TN" or "Nashville, Tennessee"); a city not in the list is reported when the search is saved | Adzuna's `distance` let a job 39.7 mi away through a 25 mi search; the spec allows no geocoding service | Yes (option b, 2026-10-05) |
| 2026-10-05 | The salary range isn't sent to Adzuna; the app checks it after fetching, against salaries stated in the posting only. Jobs with no salary, or only Adzuna's estimate, are kept and labeled ("Not listed" or "est.") | Adzuna's salary filter also applies to its estimates (34 of 39 live results), so jobs that never stated a salary were removed on a guess. Spec said the range is "sent to Adzuna's salary filters and checked again after fetching" | Yes (option b, 2026-10-05) |
| 2026-10-05 | "Hide jobs with no salary listed" hides only jobs with no salary at all; jobs with an Adzuna estimate stay visible, labeled "est." | Most Adzuna results have only an estimate (36 of 41 live), so hiding them would hide most jobs | Yes (2026-10-05) |
| 2026-10-05 | Word limit after drafting: humanize and the claim fix-up are told the word limit (400, or 250 for Short). If a generated letter is still over it after either step, a trim step (`agent/prompts/trim.md`, effort `low`) cuts it to 20 words under the limit or less, removing words only. Trimming runs before verify, so the trimmed letter is checked. No call when the letter is within the limit; your own edits are never trimmed. `scripts/eval.py` runs the same steps and reports the trim cuts | Posting 09 went from 394 to 404 words after those steps, and nothing checked the length again | Yes (2026-10-05) |
| 2026-10-05 | Fit scoring is batched: one Claude call (`agent/prompts/score_jobs.md`, Opus 5.5 at effort `low`) reads up to 10 postings with the resume and returns, for each, the work setting (remote / hybrid / on-site / unknown), a fit from 1 to 5 and a one-line reason. Up to 4 calls run at once. It doesn't reuse Parse and Match | Spec says to reuse Parse and Match (2 calls per job). Adzuna descriptions are cut at 500 characters, so Match has little to work with; batching costs about $0.50 a run instead of $2–4 | Yes (2026-10-05) |
| 2026-10-05 | Every new posting that passes the date, salary and exclusion rules is sent to Claude, including the nationwide remote query's results whose text doesn't say remote. Claude's label replaces the keyword guess, then the work-setting and location rules run. Postings already in the app aren't scored again (matched by source ID or by company, title and place, as given or as remote) | Spec: "kept only if Claude confirms the posting is remote"; about $0.30 a run more than checking only snippets that mention remote | Yes (2026-10-05) |
| 2026-10-05 | If scoring fails (no API key, no resume, out of credits or an API error), the jobs are still stored with the keyword label and no fit, sorted last with a dash, and the problem is shown after the run | A failed Claude call shouldn't lose a run's Adzuna results | n/a |
| 2026-10-05 | `jobs` gets `fit` and `fit_reason` columns; `init_db` adds missing columns to an existing database (`ADDED_COLUMNS` in `storage/db.py`). The shortlist is sorted by fit, then date, with unscored jobs last | Databases created in Milestone 10 already have a `jobs` table, which `CREATE TABLE IF NOT EXISTS` skips | n/a |
| 2026-10-05 | Acceptance check script `scripts/label_jobs.py`: writes 20 scored postings (a mix of Claude's settings, newest first) to `output/job_labels/<date-time>/labels.csv` for you to label (`your_setting`, x in `your_pick` for your top 5), and `--check` reports settings right out of 20 and how your picks compare with Claude's top scores | Spec: 20 hand-labeled postings and your own top picks | n/a |
| 2026-10-05 | Start letter: watch-list jobs (full text stored) create an application linked to the job (`applications.job_id`), mark the job Applying and draft straight to the review screen. Adzuna jobs open New cover letter with the link filled in, the paste box open and a note, because Adzuna's job links return a CloudFront "Request blocked" page to the app; the app doesn't get around bot protection. A job that already has a letter opens it. New "Applying" tab with Open letter | Spec: Start letter fetches the full posting from the job's link; Adzuna blocks that | Yes (2026-10-05) |
| 2026-10-05 | The fetcher follows redirects one hop at a time and stops before requesting any site on the no-fetch list (LinkedIn, Indeed, Glassdoor, Jobright, HiringCafe), at most 5 hops | It checked only the link you gave, so an aggregator link redirecting to Indeed would have been read | n/a |
| 2026-10-05 | Daily run: APScheduler `BackgroundScheduler` inside the app's server process (`search/schedule.py`), started once on app start-up; on/off and time on a Daily run card on Find jobs (stored in a new `app_settings` table). A run missed while the app was closed happens when the app is next opened, unless a search already ran since that day's time; a run missed while the computer slept still happens within 6 hours. Scheduled and on-demand runs never overlap. The last scheduled run's outcome shows on the card; the sidebar shows "Find jobs · N new" | Spec: daily schedule with APScheduler while the computer is on; "New jobs" count in the app. The server must be running (open the app once after starting it) | Yes (in-app scheduler, 2026-10-05) |
| 2026-10-05 | Company watch list: new `watch_companies` table; companies are added on Profile & resume by pasting a careers link (Greenhouse, Lever or Ashby), checked with one call to the board. Each run reads every board once; a job is matched to a search when all the words of one of its titles appear in the job title. It qualifies as remote (anywhere in the US; Lever and Ashby give the country) or near a city (its locations are looked up in the places list). A board's own remote/hybrid/on-site label (Lever, Ashby) is trusted over Claude's. Descriptions sent for scoring are capped at 3,000 characters; the full text is stored | Spec: watch list matched by title after fetching; one free call per company per run | n/a |
| 2026-10-05 | When two postings share a duplicate key, each is checked against the rules on its own data, and the first copy that qualifies is the one stored | A UK-only remote job was kept because a US copy with the same key qualified | n/a |
| 2026-10-05 | Watch-list jobs skip the date rule: every open job that matches a search's titles, locations, salary and exclusions is collected; jobs already seen aren't new again, so after the first run only newly posted ones appear | Spec: watch-list jobs filtered by posted date. Boards keep jobs open for months, and every match on 5 real boards was older than 3 days | Yes (2026-10-05) |
| 2026-10-05 | Application profile in `data/application_profile.yaml` (`storage/application_profile.py`): street, apartment, city, state, ZIP, country; authorized to work in the US and need sponsorship (Yes / No); willing to relocate (Open to it / Yes / No); earliest start; how you usually hear about jobs; optional salary answer. Every choice has "Not set", and blank or Not set means the agent leaves the question for you. Edited on an "Application answers" card on Profile & resume and saved with Save changes | Spec's application profile fields and the mockup's Application answers card; the address is split because forms ask for it in parts | n/a |
| 2026-10-05 | `saved_answers` table: question, a normalized question key (unique, so rewordings in case or punctuation replace rather than duplicate), answer, times used, created, updated and last used. Similar questions are matched by the higher of word overlap (ignoring filler words) and character similarity, with a threshold of 0.6. Managed on a "Saved answers to past questions" card | Spec: offered for reuse on similar questions; Milestone 8 will offer them while filling forms | n/a |
| 2026-10-05 | Playwright 1.63 drives your installed Google Chrome (`channel="chrome"`) with the app's own persistent profile in `data/browser_profile` (gitignored); no separate browser download | User approved the install; the spec's dedicated Chrome profile | Yes (2026-10-05) |
| 2026-10-05 | Each filling session runs in its own worker thread (Playwright must stay on the thread that started it; Streamlit reruns on others). The Fill application screen sends it commands (confirm, resume, continue, stop, close) and refreshes every 1.5 seconds while it works. One session at a time. The browser stays open at the end so you can submit | Streamlit and Playwright's threading | n/a |
| 2026-10-05 | Code-level rules: every agent click goes through `apply/guard.safe_click`, which refuses submit-type controls and anything labeled submit, apply, send, finish, confirm or accept; text is entered with `fill` (never Enter). Demographic/EEO questions (race, ethnicity, gender, pronouns, sexual orientation, veteran, disability, self-identification), attestations, certifications and consent questions are never sent to Claude and never filled. Single checkboxes are left for you. Choices must be one of the field's options; salary only from a saved salary answer; text answers not found in their source are filled but marked for review | Spec guardrails, enforced independently of the model | n/a |
| 2026-10-05 | Field mapping: one Claude call per page (`agent/prompts/map_fields.md`, effort `medium`) with the fields, profile, application answers, saved answers, resume and which files exist. Free-text screening questions are left for you until Milestone 8 drafts them | Spec: Claude maps fields; drafting screening answers is Milestone 8 | n/a |
| 2026-10-05 | Finding the form: the browser follows the link; navigation to LinkedIn, Indeed, Glassdoor, Jobright and HiringCafe is blocked (and a page that redirects there stops before it's read); on a posting page the Apply *link* is opened by its address (buttons are never pressed); embedded Greenhouse forms are opened directly. Real Adzuna links answer the app's automated browser with HTTP 403 ("suspicious behaviour"), so the agent stops, says so, and the Fill application screen offers a box for the company's own link | The app doesn't get around bot protection; this changes the "reaches the right form from Adzuna links" acceptance item | Pending |
| 2026-10-05 | Milestone 7 starts only from an application with an approved letter (Fill application on the review and detail screens). The approved letter is uploaded as a PDF (a .docx if no PDF maker is installed) and pasted into cover-letter text boxes | Spec: Fill application is from an approved letter; Fill without cover letter is Milestone 8 | n/a |
| 2026-10-01 | Find jobs screen per the mockup, minus the Fit column (Milestone 11) and Start letter (Milestone 12). Job titles link to the posting; Save / Dismiss / Move to New change the job's status | Milestone 10 scope | n/a |
| 2026-10-01 | Upload limit 10 MB; `fpdf2` is used only to regenerate the PDF test fixtures and isn't in `requirements.txt` | Resumes are small; avoid a runtime dependency | n/a |

## Blockers & open questions

- [ ] Milestone 7 live check: fill in your application answers, then choose 5 real Greenhouse or Lever postings you'd consider applying to. Each needs an application with an approved letter (about $0.10 per letter, a few cents per form mapping). The agent then fills each form in a visible Chrome window with your real details, never submitting; you watch, and we count fields filled correctly (target 90% of non-sensitive fields)
- [ ] Approve or change the Adzuna-link decision: Adzuna blocks the app's browser (HTTP 403), so for Adzuna jobs you paste the company's link on the Fill application screen

- [x] Watch-list dates: the date rule is skipped for watch-list jobs (user's choice, 2026-10-05)
- [x] Watch list: OnePay and Realm (Ashby) added 2026-10-05 for the live check (you had no preference; both are companies you've applied to). Remove or add more on Profile & resume
- [x] Milestone 12 live checks: run with the watch list and Start letter done 2026-10-05; scheduled-run live check skipped by your choice

- [ ] Work setting from snippets: Adzuna descriptions stop at 500 characters, so Claude labeled 27 of 41 live jobs "unknown" (mostly Nashville city results), and 9 of the 20 postings on the labeling sheet. If the full postings say hybrid or on-site, those count as wrong, and the 17-of-20 target can't be met. Possible fix after labeling: for city results Claude can't label, read the full posting from the job's link (as Start letter will in Milestone 12), skipping sites that forbid automated reading

- [ ] Confirm the defaults listed in the spec's "Open questions & defaults assumed" table with the user
- [ ] Get a writing sample (for example, a past cover letter) from the user for the profile
- [x] Adzuna keys added to `cover-letter-agent/.env` (done by 2026-10-05). Anthropic key: done
- [x] Adzuna's `distance` isn't exact (a 25 mi Knoxville search returned a Morristown, TN job 39.7 mi away). User chose option (b), checking the job's coordinates; built 2026-10-05
- [x] Live search with a salary range: done 2026-10-05 ($90k minimum)
- [x] Estimated salaries and the salary filter: Adzuna's `salary_min` filter also applied to its own estimates and removed postings that never stated a salary. User chose option (b), filtering on stated salaries in the app; built 2026-10-05
- [x] Fonts: bundle locally (approved 2026-10-01)
- [x] Approve or change the "Pending" rows in Decisions & deviations (all approved 2026-10-01)
- [x] Git repository initialized at the workspace root (2026-10-01); first commit pushed to github.com/evanreynolds1116/JobAgents (`main`)
- [x] Upload your real resume and confirm nothing is missing (confirmed 2026-10-01)
- [x] Split `app.py` into one file per screen under `ui/`: done 2026-10-01
- [x] Milestone 3 acceptance: 10 real links received 2026-10-01; 8 of 8 readable postings correct (see session log)
- [x] Draft speed: match effort lowered to `low` (2026-10-01); slowest real posting went from 66 to 45 seconds
- [x] API credits added (2026-10-01)
- [x] Text of LinkedIn postings 09 (The Home Depot, Software Engineer (Remote)) and 10 (Hatch, Backend Engineer II) received 2026-10-05; saved as `tests/fixtures/real/09.txt` and `10.txt`, each starting with the company and title lines the user gave, and added to `postings.json`
- [x] Unsupported claims: 5 of 6 evaluated letters had 1–2 flagged embellishments. User chose option (a), an automatic fix-up pass (built 2026-10-01; not yet run against the live API because credits ran out)
- [ ] Score the judgment calls in `output/eval/2026-10-01_133720/scores.csv` (postings 01–08), `output/eval/2026-10-05_113129/scores.csv` (10) and `output/eval/2026-10-05_114543/scores.csv` (09, re-run) (sounds like you, specific to the company, would send after light edits), and say which postings are weak matches for your resume
- [x] Letter length after the rewriting steps: posting 09's draft was 394 words, but the humanize and fix-up steps took it to 404. Fixed 2026-10-05 (user approved): both steps get the word limit, and a trim step runs when a letter is still over it (see Decisions)
- [x] Draft speed with all five steps: 85 seconds on a real posting. Verify kept at `medium` (2026-10-01); about 85 seconds per letter is accepted, against the spec's "under a minute" goal
- [x] Real postings go in a gitignored `tests/fixtures/real/` (approved 2026-10-01)
- [x] Refusal fallback and skipping LinkedIn/Indeed-type sites approved 2026-10-01

## Session log

### 2026-10-05 (Milestone 7, build)
- Installed Playwright 1.63 (your OK) and confirmed it drives Chrome 154. Probed a real Greenhouse form (Axios) and a real Lever form (Palantir) read-only to learn their structure (saved in the gitignored `tests/fixtures/real/forms/`): Greenhouse uses searchable dropdowns (react-select) for country, location, how-did-you-hear and authorization questions; Lever uses plain inputs and radio and checkbox groups with the question in a wrapper.
- Built `apply/`: `guard.py` (blocked Submit, sensitive and attestation detection), `extract.py` (field reading, including opening each dropdown to read its options; correct labels for all 24 Greenhouse and 22 Lever fields on the real forms), `mapping.py` (Claude proposal plus code rules), `fill.py`, `resolve.py`, `session.py` (worker thread), `start.py`. Storage `filled_answers` (`storage/filled.py`). Screen `ui/apply.py` per the mockup; Fill application buttons on review and detail; detail page "Your answers" tab.
- Found while building: the job-board blocker handed requests to the network and skipped other handlers (fixed); Playwright doesn't route the target of a server redirect, so pages are also checked after loading; an edit dropped a function header (caught by the run).
- Read-only live checks: a real Ashby link reached its application form; two real Adzuna links were refused with HTTP 403 "Access Denied" (now reported clearly, with a box for the company's link).
- Tests: 375 passed, 1 skipped. New: `test_apply_rules.py` (sensitive and attestation labels from the real forms, Submit detection, every mapping rule, sensitive fields never sent to Claude), `test_apply_browser.py` (headless offline Chrome on made-up Greenhouse- and Lever-shaped forms: reading, filling, dropdowns and search boxes, outlines, Submit never clicked including a cookie banner, hidden instructions ignored, link resolution for 8 cases, a whole session from an Adzuna link to hand-over with answers recorded, the login pause, the job-board stop), `test_apply_ui.py`.

### 2026-10-05 (Milestone 6)
- Built the application profile (`storage/application_profile.py`) and saved answers (`storage/answers.py`, `saved_answers` table), with two new cards on Profile & resume: Application answers (saved with Save changes, included in the unsaved-changes notice, warnings for contradictory authorization and sponsorship answers and malformed US ZIP codes) and Saved answers to past questions (add, edit, delete, times used).
- Found while testing: saving a question that clashed with another saved one closed the database connection before reporting it, which crashed instead of showing the message; fixed.
- Checked in the running app: at the narrow pane width the three-across layout broke labels mid-word, so the answers use two columns. No server errors.
- Tests: 308 passed, 1 skipped. New: `test_application_profile.py` (defaults, round trip, hand-edited YAML, warnings, saved answers add/update/delete/clash, similar-question lookup, reuse count) and three Profile screen tests (enter, save, reopen and edit every field; warnings; saved answers on screen).
- Your answers aren't filled in yet: they're yours to enter on Profile & resume.

### 2026-10-05 (Milestone 12, live checks)
- Per your choices: watch-list jobs skip the date rule; live check of a run plus Start letter (not the scheduled run).
- In the running app (database backed up first): added OnePay and Realm on Profile & resume. Ashby doesn't give a company name, so the first add showed "Oneapp"; adding again with the name filled in renamed it. Ran the search: 6 Adzuna calls (42 of 250 today) and 2 watch-list companies, 19 new jobs, 62 already seen and not scored again, Claude checked 77 postings. The 9 watch-list jobs: OnePay "Software Engineer, Risk" 5; OnePay "Product Facing", OnePay "Credit Card" (the one you applied to) and Realm "Backend" 4; interns and new-grad roles 1–2.
- Clicked Start letter on OnePay "Software Engineer, Risk": drafted, smoothed, checked and fixed up, then opened on the review screen (about 2.5 minutes; 350 words; 17 claims checked, 2 left for you to review, 2 style flags). The application is linked to the job, which moved to Applying. No server errors.
- Noticed: OnePay's board labels its internship "Remote" while the text says NYC 3–4 days a week; board labels are trusted over Claude's reading, so it shows as remote (scored 1, so it sits at the bottom).
- Tests: 298 passed, 1 skipped.

### 2026-10-05 (Milestone 12, build)
- Built Start letter (`ui/find_jobs.py`, `ui/new_letter.py`), the daily run (`search/schedule.py`, APScheduler 3.11.3 added to `requirements.txt`), the company watch list (`search/watchlist.py`, Profile & resume card, run integration), the fetcher's redirect check, and the duplicate fix above. User decisions: Adzuna jobs open New cover letter ready to paste; scheduler inside the app.
- Found while building: Adzuna's job links are blocked for the app (CloudFront 403), so neither Start letter nor the Milestone 11 "unknown" fix can read full Adzuna postings.
- Live, free: read the Axios (Greenhouse), Realm, OnePay and Tessera Labs (Ashby) and Palantir (Lever) boards with the saved search's rules: all reachable; every title match was older than 3 days (see Blockers). Checked Find jobs (Start letter, Applying tab, Daily run card, "Find jobs · 41 new") and the Profile watch-list card in the running app; widened the actions column so the three buttons fit on one line; no server errors.
- Tests: 298 passed, 1 skipped. New: `test_watchlist.py` (board links, the three APIs' shapes, title matching, locations, a run with the watch list, duplicates judged on their own copy, storage), `test_schedule.py` (a second scheduled run adds 0 new jobs, problems recorded, no overlapping runs, missed runs, scheduling, start-up once, status text), Start letter for watch-list and Adzuna jobs, the redirect check, the watch-list card.

### 2026-10-05 (Milestone 11, build)
- Built Claude's work-setting labels and fit scores: `search/score.py` and `agent/prompts/score_jobs.md` (batches of 10, 4 at a time); `search/run.py` now collects each posting once with every query that found it, applies the date, salary and exclusion rules, skips postings already in the app, scores the rest, then runs the work-setting and location rules on Claude's labels. Fit and reason stored in new `jobs` columns (an existing database gets them on start-up). Find jobs shows the Fit square and reason from the mockup and sorts by fit, then date. Acceptance sheet script `scripts/label_jobs.py`.
- User decisions: batched scoring instead of Parse + Match per job; check every remote-query posting with Claude.
- Tests: 257 passed, 1 skipped. New: Claude's label decides the setting (kept from the remote query, dropped as on-site), sorting by fit, only new postings scored, a known job relabeled remote isn't scored again, a scoring failure keeps the jobs, batch request contents and tag escaping, a missing posting in the reply, batching and partial failure, no key or resume, the database upgrade, the Fit column, and the labeling sheet.
- Live run in the app (user approved; `app.db` backed up first): saved the search "Software and backend engineering" (Software Engineer and Backend Engineer; Nashville, TN and Knoxville, TN, 25 mi; remote + hybrid; last 3 days) and ran it. 6 Adzuna calls (36 of 250 today), Claude checked 111 postings, 30 seconds in total, no errors. 41 new jobs: 13 remote, 1 hybrid, 27 unknown. Fits: one 5, seven 4s, fourteen 3s, fifteen 2s, four 1s. Reasons are specific and seniority is weighed (principal, lead and manager roles get 1–2 against 5 years; "Java and Spring Boot absent from resume").
- Checked the Find jobs screen in the running app: Fit squares and reasons match the mockup, sorted by fit; no server errors.
- Wrote the labeling sheet: 10 remote, 1 hybrid, 9 unknown.

### 2026-10-05 (letter length fix)
- Built the length fix the user approved: humanize and the fix-up get the word limit; a new trim step cuts letters still over it, before verify. Wired into the app (`ui/drafting.py`) and `scripts/eval.py` (new "trim cuts" in the report). Your own edits are never trimmed. "What happens next" on New cover letter mentions the trim.
- Tests: 244 passed, 1 skipped. New: word limits, humanize and fix-up receive the limit, trim skips the call within the limit, trim sends the count and target, a long letter is trimmed before checking, Short uses 250, hand edits aren't trimmed.
- Re-ran posting 09 (`output/eval/2026-10-05_114543/`): 374 words (draft 374; humanize changed nothing; the fix-up corrected one quote from the posting to match it word for word, with no change in length). 0 unsupported claims, 0 banned phrases, 4 style flags, 108 seconds. Within length, but the trim step never ran, because this draft came in shorter. It's covered by tests but hasn't yet run on a real letter.

### 2026-10-05 (Milestone 5, postings 09–10)
- Saved the pasted text of the two LinkedIn postings as `tests/fixtures/real/09.txt` (The Home Depot, Software Engineer (Remote)) and `10.txt` (Hatch, Backend Engineer II), and added their expected company and title to `postings.json`.
- Ran `scripts/eval.py --only 09,10` (`output/eval/2026-10-05_113129/`): 2 of 2 correct company and title; 2 of 2 with zero unsupported claims after the fix-up (0 of 2 before; changes were narrow, for example "AI-assisted development is part of my everyday work" became "...a big part of how I work now"); 2 of 2 with no banned phrases; 1 of 2 within length (09: 404 words, 10: 394); 1 and 3 style flags; 120 and 118 seconds.
- 09 shows "2 of 4 must-haves with evidence": the two missing are "18 or older" and "allowed to work in the U.S.", which a resume doesn't show, so this isn't a weakness in the letter.
- Open: letter length after the rewriting steps (see Blockers); your scores for both runs.

### 2026-10-05 (Milestone 10, salary check)
- Live run with a $90k minimum (same search, temporary database, calls added to the app's count). Sent `salary_min=90000` with `salary_include_unknown=1`. 39 new jobs, 0 duplicates, none older than 3 days, every one with a range reaching $90k (lowest top of range $94,452; one range of $82k–$136k kept because it overlaps). The app's own salary rule dropped nothing because Adzuna had already applied the minimum. Compared with an unfiltered run a minute earlier, the minimum removed exactly two jobs, both Vontier "Software Engineer II" with estimated salaries of $70,719 and $75,238.
- 6 calls were wasted: a failed script edit wasn't chained to the run, so the search ran once without the minimum. Adzuna calls today: 24 of 250.
- Milestone 10 marked Done: every acceptance item checked; tests 236 passed, 1 skipped.
- Then, per the user's choice (option b): the salary range is no longer sent to Adzuna; the app filters on stated salaries only and keeps estimate-only jobs labeled "est.". Tests: 236 passed, 1 skipped (new: an estimate-only job below the range is kept; no salary parameters are sent). Live re-run with the $90k minimum: no salary parameters sent; 41 new jobs, the same as with no minimum, including both Vontier jobs labeled as estimates; no stated salary under $90k came back. Adzuna calls today: 30 of 250.

### 2026-10-05 (Milestone 10, distance check)
- Built the radius check the user chose (option b): `search/places.py` (offline city lookup and distance), `search/us_places.csv` and `scripts/build_places.py` (from the Census Gazetteer, downloaded with the user's OK). Results from city queries that aren't remote are dropped if the job's coordinates are farther than the radius from the city, reported as "outside your cities' radius". Saving a search with a city that isn't in the list shows a message.
- Tests: 236 passed, 1 skipped. New: city lookup and distance, the radius check (remote jobs and unknown cities skipped, jobs without coordinates kept), the unknown-city message; the acceptance scenario now includes a Morristown job that gets dropped and a job without coordinates that's kept.
- Live re-run (same search, new temporary database, 6 more calls added to the app's count, now 12 today): 41 new; the Morristown job was dropped as outside the radius. City results left: Nashville (26), La Vergne (1) and Knoxville (1); 0 duplicates; none older than 3 days.

### 2026-10-05 (Milestone 10, live Adzuna check)
- Ran the live check with a temporary database (scratchpad only; app data untouched): Software Engineer and Backend Engineer; Nashville, TN and Knoxville, TN (25 mi); remote + hybrid; last 3 days; no salary range. The 6 calls were then added to the app's Adzuna usage count. The real `app.db` got the new Milestone 10 tables (`saved_searches`, `jobs`, `api_usage`) from `init_db`, which the app also runs on start-up, and was backed up first.
- Results: 6 calls, no errors. 147 found: 43 new, 12 repeats across queries, 69 non-remote results from the nationwide queries dropped, 22 older than 3 days, 1 on-site. Results per query: Software Engineer had 50 near Nashville, 3 near Knoxville and 50 remote; Backend Engineer had 2 near Nashville, 0 near Knoxville and 42 remote.
- Stored: 0 duplicates; all posted 2026-10-02 to 2026-10-05. Work settings: 13 remote, 1 hybrid and 29 unknown (Milestone 11's classifier will sort out the unknowns). City results were in Nashville (26), La Vergne (1) and Knoxville (2), plus one Morristown result outside the radius (see Blockers). Every result had a salary: 38 Adzuna estimates and 5 from the posting.
- Tests: 233 passed, 1 skipped.
- Next: decide on the radius issue; run a live search with a salary range.

### 2026-10-01 (Milestone 10)
- Worked on: Milestone 10, saved searches and Adzuna (Milestone 5 still open for the user's scores and postings 09–10)
- Completed: Adzuna parameters checked against Adzuna's published OpenAPI spec. Saved search criteria (titles, cities with radius, work settings, salary range, date posted, excluded companies and keywords) with validation. Query builder (one query per title per city plus one nationwide remote query per title). Normalization, work-setting labels from the text, duplicate removal across queries, sources and runs. Date, salary, exclusion and location rules. Adzuna usage tracking with the daily and monthly limits. Find jobs screen: last run, Edit searches, Run search now, saved-search card with "Adzuna calls today", New / Saved / Dismissed with counts, hide-no-salary toggle, Save / Dismiss / Move to New. Adzuna keys in `.env` and `.env.example`, and their status on Profile & resume.
- Found while checking the screen: salaries like "$95k–$120k" rendered as math formatting; fixed.
- Tests: 233 passed, 1 skipped. New: `test_search.py` (acceptance scenario with made-up Adzuna responses: 2 titles × 2 cities, last 3 days; parameters; re-runs; date filter; allowance; errors) and `test_find_jobs_ui.py`.
- Next: Adzuna keys for the live check.

### 2026-10-01 (Milestone 5, second evaluation)
- Re-ran `scripts/eval.py` on postings 01–08 with the automatic fix-up (`output/eval/2026-10-01_133720/`). Results: 8 of 8 correct company and title; 8 of 8 with zero unsupported claims (2 of 8 before the fix-up, so the fix-up resolved 6 letters with 1–2 claims each); 8 of 8 with no banned phrases; 8 of 8 within 250–400 words (363–398); 1–4 style flags per letter left for review; 72–130 seconds per letter (average 105).
- Fix-up changes were narrow and accurate, e.g. "Python, SQL and TypeScript" → "Python and SQL, with TypeScript in my personal projects"; "grow my AWS skills" → "pick up AWS"; removed an unstated "Before any code was generated".
- Still needed for Milestone 5: postings 09 and 10 (LinkedIn text), and the user's scores for the judgment calls.

### 2026-10-01 (Milestone 5, fix-up pass)
- Built the automatic fix-up pass (option a) in the pipeline, the shared drafting flow (new letters and redrafts) and `scripts/eval.py`, whose report now shows unsupported-claim counts before and after the fix-up. New cover letter screen text updated ("Usually one to two minutes").
- Tests: 197 passed, 1 skipped. The fix-up prompt hasn't been run against the live API yet (no credits); the next evaluation run will be its first real test.

### 2026-10-01 (Milestone 5, in progress)
- Worked on: Milestone 5, export, history and evaluation
- Completed: .docx export (simple header with name and contact details) and PDF via docx2pdf/Word in a separate process, gated on approval and always using the approved version; download button on the review screen. Applications list per the mockup (search, All / In progress / Submitted / Archived with counts, status, letter state with flag counts, last activity, next-step button). Application detail per the mockup (key dates, saved job description, letter sent, "Your answers" placeholder for Phase 2, dated notes log, Mark as submitted, Archive, Restore). `scripts/eval.py` with a gitignored manifest of the 10 real postings. Remaining spec tests added (job notes supported by notes in the verifier; export refused for drafts).
- Tests: 187 passed, 1 skipped (real Word conversion, passed when run on demand).
- First quality evaluation (`output/eval/2026-10-01_131103/`): 01–06 ran; 07 and 08 failed because the API credit balance ran out; 09 and 10 skipped (no text yet). Results: 6 of 6 correct company and title; 0 banned phrases in all 6; 5 of 6 within 250–400 words (Cohere at 410); 1 of 6 with zero unsupported claims (5 had 1–2 flagged embellishments); 78–97 seconds per letter (average 87).
- Fixes from the run: a clear "out of API credits" message instead of the raw API error; the evaluation's "names the company" check now accepts the short name ("Regal" for "Regal Cinemas"). Tests: 193 passed, 1 skipped.

### 2026-10-01 (Milestone 4)
- Worked on: Milestone 4, verify, review and approve
- Completed: Phrase linter (`agent/lint.py`). Pipeline steps 4 (humanize) and 5 (verify) with new prompts, plus revision support in step 3. Every draft now runs all five steps; if humanize or verify fails, the draft is still saved unchecked and the review screen offers "Check again". Review screen rebuilt per the mockup: status chip, Approve (locked until flags are reviewed), letter with unsupported claims (red) and style issues (amber) highlighted with hover reasons, inline editing, "Needs your review" panel with Remove sentence / It's true: add to notes / Rewrite this sentence, Ask for changes, How you match, Versions (view and restore), editable job notes, posting summary, and disabled export buttons. Storage: approve, return to draft on any new version, export gate. Profile: banned-phrase list editor.
- Live checks (made-up data, recorded for tests): the verifier flagged an inserted false claim ("led a team of 12 engineers at Google") and also caught smaller embellishments. On real posting 04 with the user's resume: 85 seconds for all five steps, 18 claims checked; one false flag traced to a PDF line break in the resume and fixed.
- Tests: 163 passed. New: `test_lint.py` (every banned phrase in any case), steps 4 and 5 in `test_pipeline.py` (including the false-claim acceptance test), approval and export gate in `test_db.py`, review-screen flows in `test_drafting_ui.py`, phrase editor in `test_profile.py`.
- Next: decide verify effort; user tries the review screen; Milestone 5

### 2026-10-01 (Milestone 3 acceptance)
- Ran the user's 10 posting links through the app's fetcher. Read automatically: 02 OnePay, 03 Tilt, 05 Realm, 06 Cohere, 08 Tessera Labs (Ashby/Rippling, via embedded JobPosting data) and 04 Axios (Greenhouse, after raising the timeout). Fell back to paste as designed: 01 Regal (UltiPro, JavaScript page), 07 Versant (SmartRecruiters, JavaScript page), 09 and 10 (LinkedIn, not requested). Stand-ins for the pasted text of 01 and 07 came from the saved page data and SmartRecruiters' public postings API.
- Full pipeline on 01–08 with the user's resume and profile: 8 of 8 correct company and title, no invented evidence quotes dropped, 359–410 words, 44–66 seconds each. Milestone 3 Done.
- Fetcher fixes found by the run: timeout 20 → 30 seconds (Greenhouse took 16 s), "unsupported browser" pages reported as JavaScript pages, Jobright's `jr_id` ignored when spotting duplicate links. Postings and results are in the gitignored `tests/fixtures/real/`.
- Tests: 100 passed.
- Follow-up: match effort lowered to `low` at the user's request; posting 04 (Axios) re-run in 45 seconds instead of 66, still correct.

### 2026-10-01 (Milestone 3)
- Worked on: Milestone 3, fetch and draft
- Completed: Split the UI into `ui/` (setup, profile, new letter, review, placeholders, navigation, shared style). New cover letter screen per the mockup: job link, paste fallback, notes, tone and length, "What happens next". Fetcher (`agent/fetch.py`) with JSON-LD JobPosting support, login-wall/JavaScript-shell/HTTP-error detection and a 30,000-character cap. Pipeline steps 1 to 3 (`agent/pipeline.py`, prompts in `agent/prompts/`) using structured outputs, 3 SDK retries with backoff, one retry on invalid JSON with a debug panel, clear messages for API errors and refusals, and a code check that drops invented evidence quotes. Saves after every step; "Try again" resumes where it stopped. Same-URL detection with "Open it" / "Draft a new version". Confirm-company-and-title step when the parse is unclear. Basic review screen with posting summary, match, draft in Source Serif 4, versions and plain text to copy. Switched to `claude-opus-5-5` at the user's request.
- Live check (made-up resume and postings only): 3 of 3 postings got the right company, title and contact; the prompt-injection posting produced a normal letter; about 26 seconds per letter. Tightened the draft prompt after spotting invented details ("last spring", "I haven't spent much time on a river").
- Tests: 97 passed (`pytest`), none calling the API. New: `test_fetch.py`, `test_pipeline.py` (recorded responses), `test_drafting_ui.py`, plus query tests in `test_db.py`.
- Next: user supplies 10 real postings for the acceptance check; then Milestone 4

### 2026-10-01 (Milestone 2 follow-up)
- User confirmed their real resume converted with nothing missing: Milestone 2 Done.
- Added a country code field before Phone and split the link into LinkedIn and Portfolio or website, with warnings for a malformed code or a LinkedIn link that isn't linkedin.com. Old single `link` values move to the right field automatically; the user's saved profile loads with no problems.
- Tests: 46 passed.

### 2026-10-01 (Milestone 2)
- Worked on: Milestone 2, resume and profile
- Completed: Resume upload (PDF or .docx) on Profile & resume, converted to `data/resume.md` with headings and bullets; original kept as `data/resume_original.*`. Converter handles two-column PDFs (header kept whole, then each column top to bottom), plus .docx page headers, tables, text boxes and hyperlinks; scanned or damaged files show a clear message. Editable converted text, profile form (name, email, phone, city, link, tone, length, sign-off, always/never mention), one or more writing samples, Save changes with an unsaved-changes notice and light email/link warnings. Profile saved to `data/profile.yaml` in readable YAML. `resume.text_hash()` ready for drafts. Mockup styling: white cards, bordered 44 px inputs.
- Tests: 43 passed (`pytest`). New: `tests/test_resume.py` (made-up one- and two-column PDF fixtures, a generated .docx, error cases, storage) and `tests/test_profile.py` (YAML round trip, hand-edited files, and the screen: save, reload in a fresh session, add a sample, upload and upload errors). Also checked in the browser: typed a name, saved, restarted the server and the name and resume text were still there. Test data and the dummy key were removed afterwards.
- Next: user checks their real resume; then Milestone 3 (fetch and draft)

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
