# Job Application Assistant

A local Streamlit app with three agents that work with the Claude API. You stay in control at every handoff, and nothing is ever submitted without you.

- **Find jobs**: searches Adzuna and the job boards of companies on your watch list. Claude scores how well each job fits your resume. Searches can run once a day on a schedule.
- **Cover letters**: drafts a letter for a posting in five steps (parse, match, draft, humanize, verify). You review it, edit it, approve it and export it as .docx or PDF.
- **Fill applications**: opens the application form in Chrome and fills it from your profile, resume, saved answers and approved letter. It drafts short screening answers for you to check and pauses on each page. **It never clicks Submit.**

See `../SPEC.md` for the full spec and `../PROGRESS.md` for build status and decisions.

## What you need

- Windows 10 or 11. macOS and Linux should work with the usual path changes, but they haven't been tested.
- Python 3.12 (tested on 3.12.4), from python.org. Tick "Add python.exe to PATH" when you install it.
- Git, to download and update the app.
- Google Chrome, for filling applications. The app drives your installed Chrome and downloads no browser of its own.
- Microsoft Word or LibreOffice, for PDF export only. Export to .docx works without either.
- A Claude API key from https://console.anthropic.com/settings/keys. Drafting a letter costs about $0.10, and mapping a form costs a few cents per page.
- For job search only: free Adzuna keys from https://developer.adzuna.com/signup.

## Install

In PowerShell:

```
git clone https://github.com/evanreynolds1116/JobAgents.git
cd JobAgents\cover-letter-agent
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

In `.env`, paste your Claude key after `ANTHROPIC_API_KEY=`. For job search, also fill in `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. The file is gitignored, and the app reads it fresh, so you don't need to restart after editing it.

## Run

Double-click `run.bat`, or from this folder:

```
.venv\Scripts\streamlit run app.py
```

The app opens at http://localhost:8501. It listens on this computer only. To stop it, close the window or press Ctrl+C. Without a valid key, the app shows setup instructions instead of the main screens.

On the first run, open **Profile & resume**:

1. Upload your resume and check the converted text.
2. Fill in your details and add a writing sample.
3. Fill in your application answers and, if you like, the optional self-identification answers.
4. Click **Save changes**.

## Deploy

The app is built to run on your own computer, not on a server. Deploying it means installing it (above), starting it when you sign in, and keeping it updated and backed up.

### Start it when you sign in

The daily job search runs only while the app is running. If the scheduled time passes while the app is closed or the computer is asleep, the search runs as soon as the app is open again, unless a search has run since. To start the app automatically when you sign in to Windows, run this once from this folder in PowerShell:

```
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Job Application Assistant.lnk"); $s.TargetPath = (Resolve-Path run.bat).Path; $s.WorkingDirectory = $PWD.Path; $s.WindowStyle = 7; $s.Save()
```

This puts a shortcut in your Startup folder. It needs no admin rights. The app starts in a minimized window and opens a browser tab once it's ready. To turn this off, delete the shortcut: press Win+R, type `shell:startup` and delete "Job Application Assistant".

To set the schedule itself, go to **Find jobs** and use the schedule card.

### Update

Close the app, then from this folder:

```
git pull
.venv\Scripts\python -m pip install -r requirements.txt
```

Start the app again. Database changes are applied automatically on start-up, and your data is kept.

### Back up and move to another computer

Everything personal is in this folder and is gitignored:

| Path | What it holds |
| --- | --- |
| `.env` | Your API keys |
| `data/app.db` | Applications, letter drafts, jobs, saved answers, the watch list and settings |
| `data/profile.yaml`, `data/resume.md`, `data/resume_original.*` | Your profile and resume |
| `data/application_profile.yaml`, `data/self_id.yaml` | Application answers and self-identification answers |
| `data/browser_profile/` | The app's own Chrome profile, with sign-ins to job sites |
| `output/` | Exported letters, evaluation reports and labeling sheets |

To back up, close the app and copy `.env`, `data/` and `output/` somewhere safe. To move to another computer, install the app there as above, then copy those three back into `cover-letter-agent\`. You can skip `data/browser_profile/` and sign in to job sites again instead.

### Hosting it online

This isn't supported. The app has no login, it listens on localhost only (`.streamlit/config.toml`), it drives a Chrome window on the same computer, and the spec keeps your resume and answers on your machine. The spec leaves phone access through a host such as Streamlit Community Cloud, with a password added, for a later version.

## Using it

- **Find jobs.** Add searches with job titles, cities and a radius, a work setting (remote, hybrid or on-site), a salary minimum and a date range, then click **Run search**. Distance uses offline U.S. city coordinates (`search/us_places.csv`). Watch-list companies (Greenhouse, Lever or Ashby boards, added on Profile & resume) are checked on every search. Each job gets a fit score from Claude. Use **Start letter** to draft a letter for that job, or **More → Fill without cover letter** to go straight to the form.
- **New cover letter.** Paste a link or the posting text, add notes and draft. On the review screen you edit, approve and use **Export .docx** or **Export PDF**. Files go to `output/` as `Company - Title - Cover Letter.docx` or `.pdf`.
- **Fill application.** This button is on a letter's review screen and on the application's page. A Chrome window opens with the app's own profile. You confirm the form, the agent fills what it can, and every field shows what was entered and where it came from. Fields to review are outlined amber, and required fields left for you are outlined red. You log in, solve any CAPTCHA and click Submit yourself. Some jobs come from Adzuna, which blocks automated browsers. For those, paste the company's own job link when asked.
- **What the agent leaves for you:** legal attestations and consent boxes; demographic questions you haven't answered under self-identification (those answers never go to Claude and are matched by code); salary, unless you saved a salary answer; and anything it can't map confidently. When you type an answer it didn't have, it offers to save it for next time.

## Layout

- `app.py` runs start-up checks, the scheduler and navigation. Each screen is in `ui/`.
- `agent/` reads postings (`fetch.py`) and runs the Claude steps (`pipeline.py`). The prompts are in `agent/prompts/`.
- `search/` covers Adzuna, the watch list, filtering, fit scoring and the daily schedule.
- `apply/` is the form filler. It handles field reading, mapping, filling, link resolution, the browser session and the Submit guard (`guard.py`).
- `storage/` holds the database, profile, resume and answers code. `export/` makes the .docx and PDF files.

## Quality checks

**Cover letters.** Save postings as `tests/fixtures/real/NN.txt` and list them in `tests/fixtures/real/postings.json`, with the expected company and title, optional notes, and whether your resume is a weak match. Then run:

```
.venv\Scripts\python scripts\eval.py
```

It asks before running, because each posting costs a few cents. It writes `report.md`, one letter per posting and a `scores.csv` for your own scores to `output/eval/<date-time>/`.

**Job fit scores.** To write a sheet of 20 jobs from the app to label, then score your labels against Claude's:

```
.venv\Scripts\python scripts\label_jobs.py
```

```
.venv\Scripts\python scripts\label_jobs.py --check output\job_labels\<date-time>\labels.csv
```

## Test

Tests never call the Claude API, Adzuna or real job sites. The form tests run headless Chrome offline against made-up forms in `tests/fixtures/forms/`. Everything committed in `tests/fixtures/` is made up. Your real postings in `tests/fixtures/real/` stay out of git. After changing a prompt or schema, re-record the Claude responses with your key (this costs a few cents):

```
.venv\Scripts\python tests\fixtures\record_pipeline.py
```

Run the tests:

```
.venv\Scripts\python -m pytest
```
