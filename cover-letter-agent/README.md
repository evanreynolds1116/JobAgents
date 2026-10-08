# Job Application Assistant

A local Streamlit app with three agents that work with the Claude API. You stay in control at every handoff, and nothing is ever submitted without you.

- **Find jobs**: searches Adzuna and the job boards of companies on your watch list. Claude scores how well each job fits your resume. Searches can run once a day on a schedule.
- **Cover letters**: drafts a letter for a posting in five steps (parse, match, draft, humanize, verify). You review it, edit it, approve it and export it as .docx or PDF.
- **Fill applications**: opens the application form in Chrome and fills it from your profile, resume, saved answers and approved letter. It drafts short screening answers for you to check and pauses on each page. **It never clicks Submit.**

See `../SPEC.md` for the full spec and `../PROGRESS.md` for build status and decisions.

## What you need

- Windows 10 or 11, or a Mac running macOS 13 or later. The app is tested on Windows. The Mac steps below use the same code and libraries, but they haven't been tried on a Mac yet.
- Python 3.12 (tested on 3.12.4), from https://www.python.org/downloads/. On Windows, tick "Add python.exe to PATH" when you install it.
- Git, to download and update the app. On a Mac, running `git` the first time offers to install it.
- Google Chrome, for filling applications. The app drives your installed Chrome and downloads no browser of its own.
- Microsoft Word or LibreOffice, for PDF export only. Export to .docx works without either.
- A Claude API key from https://console.anthropic.com/settings/keys. Drafting a letter costs about $0.10, and mapping a form costs a few cents per page.
- For job search only: free Adzuna keys from https://developer.adzuna.com/signup.

## Install on Windows

In PowerShell:

```
git clone https://github.com/evanreynolds1116/JobAgents.git
cd JobAgents\cover-letter-agent
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

## Install on a Mac

1. Install Python 3.12 from https://www.python.org/downloads/macos/, and Google Chrome if you don't have it.
2. Open **Terminal** (press Cmd+Space, type Terminal and press Return).
3. Paste these lines one at a time. The first one puts the app in a folder called `JobAgents` in your home folder.

```
cd ~ && git clone https://github.com/evanreynolds1116/JobAgents.git
cd ~/JobAgents/cover-letter-agent
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
chmod +x run.command
open -e .env
```

If `python3.12` isn't found, close Terminal and open it again after installing Python, or use `python3`. Check it reports 3.12 with `python3 --version`.

## Your keys

In `.env`, paste your Claude key after `ANTHROPIC_API_KEY=`. For job search, also fill in `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. Save the file. It's gitignored, and the app reads it fresh, so you don't need to restart after editing it.

## Run

- **Windows:** double-click `run.bat`, or run `.venv\Scripts\streamlit run app.py` from this folder.
- **Mac:** double-click `run.command` in Finder. It opens in Terminal. Or run `.venv/bin/streamlit run app.py` from this folder.

After a few seconds the app opens in your browser at http://localhost:8501. It listens on this computer only. The window it runs in (Command Prompt or Terminal) is the app itself: leave it open while you use the app, and close it or press Ctrl+C to stop. Without a valid key, the app shows setup instructions instead of the main screens.

On the first run, open **Profile & resume**:

1. Upload your resume and check the converted text.
2. Fill in your details and add a writing sample.
3. Fill in your application answers and, if you like, the optional self-identification answers.
4. Click **Save changes**.

On a Mac, if double-clicking `run.command` says it can't be opened, right-click it, choose **Open**, then **Open** again; macOS remembers this. The first PDF export asks whether Terminal may control Microsoft Word. Click OK, since that's how the PDF is made.

## Deploy

The app is built to run on your own computer, not on a server. Deploying it means installing it (above), adding a desktop icon, starting it when you sign in, and keeping it updated and backed up.

### Add a desktop icon

**Windows:** run this once from this folder in PowerShell:

```
$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Job Application Assistant.lnk")); $s.TargetPath = (Resolve-Path run.bat).Path; $s.WorkingDirectory = $PWD.Path; $s.WindowStyle = 7; $s.Save()
```

**Mac:** run this once in Terminal. It puts an alias of `run.command` on your Desktop:

```
osascript -e "tell application \"Finder\" to set name of (make alias file to (POSIX file \"$HOME/JobAgents/cover-letter-agent/run.command\") at desktop) to \"Job Application Assistant\""
```

Or do it by hand: in Finder, open `JobAgents/cover-letter-agent`, hold Option+Cmd and drag `run.command` to the Desktop, then rename the alias. To keep it in the Dock instead, drag `run.command` to the right side of the Dock, next to the Trash.

Double-click the icon to start the app. If the app is already running, go to http://localhost:8501 instead. A second copy can't start while the first one is using that address.

### Start it when you sign in

The daily job search runs only while the app is running. If the scheduled time passes while the app is closed or the computer is asleep, the search runs as soon as the app is open again, unless a search has run since. To set the schedule itself, go to **Find jobs** and use the schedule card.

**Windows:** run this once from this folder in PowerShell. It puts a shortcut in your Startup folder and needs no admin rights:

```
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Job Application Assistant.lnk"); $s.TargetPath = (Resolve-Path run.bat).Path; $s.WorkingDirectory = $PWD.Path; $s.WindowStyle = 7; $s.Save()
```

The app starts in a minimized window and opens a browser tab once it's ready. To turn this off, press Win+R, type `shell:startup` and delete "Job Application Assistant".

**Mac:** open **System Settings → General → Login Items & Extensions**, click **+** under "Open at Login" and choose `run.command` in `JobAgents/cover-letter-agent`. The app then starts in a Terminal window each time you log in. To turn this off, select it in the same list and click **−**.

### Update

Close the app, then from the `cover-letter-agent` folder:

- **Windows (PowerShell):** `git pull`, then `.venv\Scripts\python -m pip install -r requirements.txt`
- **Mac (Terminal):** `cd ~/JobAgents/cover-letter-agent && git pull && .venv/bin/python -m pip install -r requirements.txt`

Start the app again. Database changes are applied automatically on start-up, and your data is kept.

### Back up

Everything personal is gitignored, so `git pull` never touches it:

| Path | What it holds |
| --- | --- |
| `.env` | Your API keys and settings, on each computer |
| `data/app.db` | Applications, letter drafts, jobs, saved answers, the watch list and settings |
| `data/profile.yaml`, `data/resume.md`, `data/resume_original.*` | Your profile and resume |
| `data/application_profile.yaml`, `data/self_id.yaml` | Application answers and self-identification answers |
| `output/` | Exported letters, evaluation reports and labeling sheets |
| `cover-letter-agent/data/browser_profile/` | The app's own Chrome profile, with sign-ins to job sites. Always on each computer |

`data/` and `output/` sit in `cover-letter-agent`, or in your sync folder if you set one up (below). To back up, quit the app and copy them, and `.env`, somewhere safe.

### Use it on two computers (OneDrive)

Your applications, letters, answers and exports can be shared between computers, such as a Windows desktop and a Mac laptop, through a OneDrive folder. Each computer keeps its own `.env` and its own Chrome sign-ins.

**Use the app on one computer at a time.** The data is a single database file, and if both computers changed it at once, OneDrive would keep one computer's changes and set the other's aside. The app checks this for you. While it's open on one computer, the other shows "Open on another computer" and waits. When you're done on one computer, click **Quit app** at the bottom of the sidebar, give OneDrive a minute to sync, then open the app on the other. If you just close the window instead, the other computer can start once the old lock has expired, within about 3 minutes.

Setup:

1. **First computer (the one with your data).** Quit the app. Create the folder `OneDrive\JobAgents`, move `data` (all of it except `browser_profile` and `upload`) and `output` from `cover-letter-agent` into it, and add a line to `.env`:
   - Windows: `SYNC_FOLDER=C:\Users\<you>\OneDrive\JobAgents`
   - Mac: `SYNC_FOLDER=~/Library/CloudStorage/OneDrive-Personal/JobAgents`
2. Start the app and check your applications are there. Then let OneDrive finish uploading (its icon shows when it's up to date).
3. **Second computer.** Install OneDrive and sign in to the same Microsoft account. On a Mac, get it from the App Store; the folder appears in Finder under Locations. Wait for the `JobAgents` folder to download. Then right-click it and choose **Always Keep on This Device**, so the database is always there in full.
4. Install the app on the second computer as above, and add its `SYNC_FOLDER` line to `.env`. Anything the second computer had of its own stays in its `cover-letter-agent/data` and is no longer used. Add any applications from it again on the shared data.
5. Turn the daily search on only once: the setting is shared, and it runs on whichever computer has the app open.

The lock goes by computer name, so give your two computers different names (they normally have them).

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

The commands here and under Test are written for Windows. On a Mac, run them from `cover-letter-agent` in Terminal with `.venv/bin/python` and forward slashes, for example `.venv/bin/python scripts/eval.py`.

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
