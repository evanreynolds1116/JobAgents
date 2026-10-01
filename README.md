# JobAgents

Planning documents for a personal, local job application assistant with three agents: job search, cover letter, and application filling. You stay in control at every handoff, and nothing is ever submitted without you.

| File | What it is |
| --- | --- |
| `SPEC.md` | The full build spec: goals, architecture, agent design, data, guardrails, testing and milestones for all three phases |
| `PROGRESS.md` | Build tracker: milestones in build order, acceptance checklists, decisions and a session log. Claude reads and updates it every session |
| `ui-mockup/` | The screen designs to match, with notes on each screen and the design tokens |

## Starting the build with Claude Code

Open this folder in Claude Code and send:

> Read SPEC.md, PROGRESS.md and ui-mockup/README.md. Then build Milestone 1 only, and update PROGRESS.md when you're done. Ask me before deviating from the spec.

Build order: milestones 1–5 (cover letter agent), then 10–12 (job search), then 6–9 (application agent).

Before you start, you'll need an Anthropic API key (from milestone 1) and a free Adzuna API key (from milestone 10).
