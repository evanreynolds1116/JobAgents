# UI mockup

These are the design mockups for the Job Application Assistant. The live, clickable version is the "Job Application Assistant UI" design canvas in Claude (seven screens; press Play on any screen to click through).

The `.dc.html` files here are each screen's source markup, saved for reference while building. They don't run on their own, but their layout, labels, colors and spacing are what the Streamlit app should match as closely as Streamlit allows.

| Screen | File | Shows |
| --- | --- | --- |
| 1. Find jobs | `Main.dc.html` | Saved search (hybrid near your cities, remote anywhere in the US), ranked shortlist with fit scores, Start letter / Save / Dismiss |
| 2. New cover letter | `NewLetter.dc.html` | Job link, optional "Notes for this job", tone and length, Generate draft or Fill without a letter |
| 3. Review and approve | `Review.dc.html` | Draft with flagged claims and style issues, requirement match, Ask for changes, versions; Approve is locked until flags are reviewed, export unlocks after approval |
| 4. Filling an application | `Apply.dc.html` | Page-by-page progress, how the agent reached the form, each field with its source and status, save-new-answer prompt; the agent never clicks Submit |
| 5. Applications | `Applications.dc.html` | Search box, status tabs, every application with its next step |
| 6. Profile and resume | `Profile.dc.html` | Resume and converted text, writing sample, contact details, application answers, company watch list, API key status |
| 7. Application detail | `ApplicationDetail.dc.html` | For when a recruiter calls: key dates, saved job description, cover letter sent, your answers, notes log |

**Design tokens used across screens**

- Fonts: Public Sans (UI), IBM Plex Mono (links, file names, counts), Source Serif 4 (the letter itself)
- Colors: sidebar `#15202B`, page `#F3F5F7`, cards `#FFFFFF` with `#D9DFE5` borders, text `#15202B` / muted `#4F5B66`, accent teal `#0F6E63` (tint `#E3F1EE`), info blue `#1F4E8C` (tint `#E6EEF8`), warning amber `#8A4B08` (tint `#FDF1E2`), error red `#A3261C` (tint `#FBE9E7`)
- Buttons and inputs at least 44 px tall; 8 px corner radius; 12 px on cards

All company names, jobs and salaries in the mockups are made up. Bracketed text like `[your title]` stands in for details from your resume.
