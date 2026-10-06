# JobAgents

A personal job application assistant that runs on your own computer. It has three agents that use the Claude API: one finds jobs, one drafts cover letters and one fills application forms. You stay in control at every handoff, and nothing is ever submitted without you.

| Path | What it is |
| --- | --- |
| `cover-letter-agent/` | The app (Streamlit). Its README covers install, running, deployment, backups and tests |
| `SPEC.md` | The full build spec: goals, architecture, agent design, data, guardrails, testing and milestones for all three phases |
| `PROGRESS.md` | Build tracker: milestones, acceptance checklists, decisions and a session log |
| `ui-mockup/` | The screen designs the app follows, with notes on each screen and the design tokens |

## Quick start

You need Python 3.12, Git, Google Chrome and a Claude API key. Free Adzuna keys are needed for job search only.

On Windows, in PowerShell:

```
git clone https://github.com/evanreynolds1116/JobAgents.git
cd JobAgents\cover-letter-agent
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

On a Mac, in Terminal:

```
cd ~ && git clone https://github.com/evanreynolds1116/JobAgents.git
cd ~/JobAgents/cover-letter-agent
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Put your keys in `.env`, then double-click `run.bat` on Windows or `run.command` on a Mac. The app opens at http://localhost:8501.

To add a desktop icon, start it when you sign in, update it, back it up or use it on a second computer, see **Deploy** in [`cover-letter-agent/README.md`](cover-letter-agent/README.md#deploy). The app is local only by design: it has no login, it listens on localhost and it drives Chrome on the same machine.

## Status

All milestones are built. A few live checks with real postings and your own labels are still open. See `PROGRESS.md`.
