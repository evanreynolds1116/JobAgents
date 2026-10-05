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

- **Current milestone:** 11. Filtering and fit scoring (5 is waiting on your scores)
- **Next step:** Start Milestone 11; separately, score the Milestone 5 evaluation (both `scores.csv` files); optionally re-run `scripts/eval.py --only 09` to see the length fix on a real letter
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
- [ ] Quality evaluation (`scripts/eval.py`) meets the success criteria in the spec's Overview & goals (all 10 postings across two runs: 10 of 10 correct company and title, 10 of 10 with zero unsupported claims, 10 of 10 with no banned phrases, 9 of 10 within 250–400 words, with 09 at 404; waiting on your scores)

### Phase 3: Job search agent

**Milestone 10. Saved searches and Adzuna**
- [x] A search for 2 titles × 2 cities over the last 3 days returns results with no duplicates (live run 2026-10-05: 43 jobs stored, 0 duplicates, 12 cross-query repeats merged)
- [x] Location rule: hybrid and on-site jobs outside the cities' radius are excluded; remote jobs from anywhere in the US are included (one nationwide remote query per title) (live 2026-10-05: 69 non-remote nationwide results dropped; city results are now checked against the job's coordinates, which dropped a Morristown, TN job 39.7 mi from Knoxville that Adzuna's 25 mi filter let through)
- [x] Date-posted and salary filters work (live 2026-10-05: none of the stored jobs was older than 3 days; with a $90k minimum, the app checks stated salaries only; two Vontier jobs with only Adzuna estimates of $71k and $75k are kept and labeled "est.")
- [x] Adzuna usage is tracked and the app pauses before the daily limit (250 calls)

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
| 2026-10-01 | Find jobs screen per the mockup, minus the Fit column (Milestone 11) and Start letter (Milestone 12). Job titles link to the posting; Save / Dismiss / Move to New change the job's status | Milestone 10 scope | n/a |
| 2026-10-01 | Upload limit 10 MB; `fpdf2` is used only to regenerate the PDF test fixtures and isn't in `requirements.txt` | Resumes are small; avoid a runtime dependency | n/a |

## Blockers & open questions

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
- [ ] Score the judgment calls in `output/eval/2026-10-01_133720/scores.csv` (postings 01–08) and `output/eval/2026-10-05_113129/scores.csv` (09–10) (sounds like you, specific to the company, would send after light edits), and say which postings are weak matches for your resume
- [x] Letter length after the rewriting steps: posting 09's draft was 394 words, but the humanize and fix-up steps took it to 404. Fixed 2026-10-05 (user approved): both steps get the word limit, and a trim step runs when a letter is still over it (see Decisions)
- [x] Draft speed with all five steps: 85 seconds on a real posting. Verify kept at `medium` (2026-10-01); about 85 seconds per letter is accepted, against the spec's "under a minute" goal
- [x] Real postings go in a gitignored `tests/fixtures/real/` (approved 2026-10-01)
- [x] Refusal fallback and skipping LinkedIn/Indeed-type sites approved 2026-10-01

## Session log

### 2026-10-05 (letter length fix)
- Built the length fix the user approved: humanize and the fix-up get the word limit; a new trim step cuts letters still over it, before verify. Wired into the app (`ui/drafting.py`) and `scripts/eval.py` (new "trim cuts" in the report). Your own edits are never trimmed. "What happens next" on New cover letter mentions the trim.
- Tests: 244 passed, 1 skipped. New: word limits, humanize and fix-up receive the limit, trim skips the call within the limit, trim sends the count and target, a long letter is trimmed before checking, Short uses 250, hand edits aren't trimmed.
- Not yet run against the live API (it costs credits); re-running posting 09 would show it on a real letter.

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
