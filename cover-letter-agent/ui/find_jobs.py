"""Find jobs screen: saved searches, run now, the daily run, and the shortlist sorted by
fit, then date, with Start letter (Milestones 10 to 12).
"""

from datetime import datetime, time
from html import escape

import streamlit as st

import config
from search import adzuna, run, schedule, watchlist
from search.criteria import DATE_OPTIONS, SETTING_LABELS, SETTINGS, City, SearchCriteria
from search.normalize import salary_label
from storage import jobs as store
from ui import dates, nav
from ui.style import muted

TABS = {"new": "New", "saved": "Saved", "applying": "Applying", "dismissed": "Dismissed"}


def source_label(source: str) -> str:
    return "via Adzuna" if source == "adzuna" else f"via watch list ({watchlist.PLATFORMS.get(source, source)})"


def posted_label(stamp: str | None, now: datetime | None = None) -> str:
    if not stamp:
        return "Date not given"
    days = ((now or datetime.now()).date() - datetime.fromisoformat(stamp).date()).days
    return "Today" if days <= 0 else ("1 day ago" if days == 1 else f"{days} days ago")


def fit_badge(fit: int | None) -> str:
    """The 1-5 square from the mockup; a dash when Claude didn't score the job."""
    if not fit:
        return '<span class="ja-fit ja-fit-none" aria-label="Not scored" title="Not scored">–</span>'
    level = "high" if fit >= 4 else ("mid" if fit == 3 else "low")
    return f'<span class="ja-fit ja-fit-{level}" aria-label="Fit {fit} of 5">{fit}</span>'


def last_run_label(stamp: str | None) -> str:
    """'today at 7:52 AM', 'yesterday', 'on Sep 28' or 'never'."""
    if not stamp:
        return "never"
    friendly = dates.friendly(stamp)
    if friendly.startswith("Today, "):
        return "today at " + friendly.removeprefix("Today, ")
    return "yesterday" if friendly == "Yesterday" else f"on {friendly}"


def _lines(text: str) -> list[str]:
    return [part.strip() for line in (text or "").splitlines() for part in line.split(",") if part.strip()]


def find_jobs_page() -> None:
    settings = config.load_settings()
    searches = store.list_searches()
    last_run = max((s["last_run_at"] for s in searches if s["last_run_at"]), default=None)

    head, actions = st.columns([3, 2], vertical_alignment="bottom")
    with head:
        st.title("Find jobs")
        counts = store.count_jobs()
        muted(f"Last run {last_run_label(last_run)} · "
              f"{counts['new']} new posting{'s' if counts['new'] != 1 else ''}")
    with actions, st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Edit searches"):
            st.session_state.fj_editing = not st.session_state.get("fj_editing", False)
            st.rerun()
        can_run = bool(searches) and settings.adzuna_status == "ok"
        if st.button("Run search now", type="primary", disabled=not can_run):
            _run(searches)

    _messages()
    if settings.adzuna_status != "ok":
        st.info("**Add your Adzuna keys to search.** Get a free app ID and key at "
                "[developer.adzuna.com/signup](https://developer.adzuna.com/signup), then add "
                "`ADZUNA_APP_ID=` and `ADZUNA_APP_KEY=` lines to `.env`. You can set up searches now.")

    if st.session_state.get("fj_editing") or not searches:
        _editor(searches)
    companies = store.list_companies()
    for saved in searches:
        _search_card(saved, companies)
    if searches:
        _schedule_card()
        _results()


def _messages() -> None:
    if flash := st.session_state.pop("fj_flash", None):
        kind, text = flash
        getattr(st, kind)(text)
    for error in st.session_state.pop("fj_errors", []):
        st.warning(error)


def _run(searches: list[dict]) -> None:
    with schedule.exclusive() as free:
        if not free:
            st.session_state.fj_flash = ("info", "The daily run is searching right now. Check back in a minute.")
            st.rerun()
        try:
            with st.spinner(f"Searching Adzuna ({run.planned_calls(searches)} calls) and your watch list, "
                            "and scoring new jobs…"):
                result = run.run_searches(searches)
        except (run.UsageLimit, adzuna.AdzunaError) as exc:
            st.session_state.fj_flash = ("error", str(exc))
        else:
            st.session_state.fj_flash = ("success", result.summary())
            st.session_state.fj_errors = result.errors
    st.rerun()


def _search_card(saved: dict, companies: list[dict]) -> None:
    criteria: SearchCriteria = saved["criteria"]
    rows = criteria.summary()
    if companies:
        rows.append(("Watch list", f"{len(companies)} compan{'ies' if len(companies) != 1 else 'y'}"))
    with st.container(border=True, key=f"card_search_{saved['id']}"):
        title, usage = st.columns([3, 2], vertical_alignment="center")
        title.subheader(f"Saved search: {saved['name']}", anchor=False)
        usage.caption(f"Adzuna calls today: {store.calls_today('adzuna')} of {run.DAILY_LIMIT} · "
                      f"this search uses {len(adzuna.build_queries(criteria))}")
        st.markdown("<br>".join(f'<span class="ja-muted">{escape(label)}</span>&nbsp;&nbsp;'
                                f'{escape(value).replace("$", "&#36;")}'  # keep $ from becoming math
                                for label, value in rows), unsafe_allow_html=True)


def schedule_status(s: dict, upcoming: datetime | None) -> str:
    """One line about the daily run: when it's next, and how the last one went."""
    if not s["enabled"]:
        text = "Off. Searches run only when you click Run search now."
    else:
        at = datetime.combine(datetime.now().date(), time.fromisoformat(s["time"]))
        text = f"Every day at {at.strftime('%I:%M %p').lstrip('0')} while the app is running."
        if upcoming:
            text += f" Next run {last_run_label(upcoming.isoformat(timespec='seconds'))}."
    if last := s["last"]:
        outcome = f"{last['new']} new job{'s' if last['new'] != 1 else ''}" if last["ok"] else last["message"]
        text += f" Last daily run {last_run_label(last['at'])}: {outcome}"
        text += "" if outcome.endswith(".") else "."
    return text


def _schedule_card() -> None:
    s = schedule.settings()
    with st.container(border=True, key="card_schedule"):
        head, toggle, when, save = st.columns([2.4, 1.2, 1.2, 1], vertical_alignment="bottom")
        head.subheader("Daily run", anchor=False)
        enabled = toggle.toggle("Run every day", value=s["enabled"], key="fj_sched_on")
        at = when.time_input("Time", value=time.fromisoformat(s["time"]), step=900, key="fj_sched_time")
        if save.button("Save time", key="fj_sched_save",
                       disabled=enabled == s["enabled"] and at.strftime("%H:%M") == s["time"]):
            schedule.save(enabled, at)
            st.session_state.fj_flash = ("success", "Daily run on." if enabled else "Daily run off.")
            st.rerun()
        st.caption(schedule_status(s, schedule.next_run()))


def _fill_without_letter(job: dict) -> None:
    """Save the job as an application with no letter and open the form filler."""
    from storage import db
    from ui.new_letter import posting_from_job

    if app_id := store.application_for_job(job["id"]):
        nav.go("apply", app=app_id)
        return
    app_id = db.create_application(job["apply_url"] or None, posting_from_job(job))
    db.update_application(app_id, job_id=job["id"], company=job["company"], title=job["title"])
    store.set_status(job["id"], "applying")
    nav.go("apply", app=app_id)


def _start_letter(job: dict) -> None:
    """One click from the shortlist: open the letter already started for this job, or start
    one on the New cover letter screen."""
    if app_id := store.application_for_job(job["id"]):
        nav.go("review", app=app_id)
    else:
        nav.go("new_letter", job=job["id"])


def _editor(searches: list[dict]) -> None:
    with st.container(border=True, key="card_search_editor"):
        st.subheader("Edit searches" if searches else "Set up a search", anchor=False)
        options = {s["id"]: s["name"] for s in searches}
        choice = st.selectbox("Search", [None, *options], format_func=lambda i: options.get(i, "New search"),
                              key="fj_edit_choice") if searches else None
        current = next((s for s in searches if s["id"] == choice), None)
        c: SearchCriteria = current["criteria"] if current else SearchCriteria()
        suffix = f"_{choice or 'new'}"

        with st.form(f"fj_form{suffix}", border=False):
            name = st.text_input("Name", value=current["name"] if current else "", placeholder="Engineering roles")
            titles = st.text_area("Job titles", value="\n".join(c.titles), height=90,
                                  placeholder="One per line, e.g. Software Engineer")
            picked = st.pills("Work setting", SETTINGS, default=c.settings, selection_mode="multi",
                              format_func=SETTING_LABELS.get)
            st.caption("Hybrid and on-site jobs must be near one of your cities. Remote jobs can be anywhere in the US.")
            rows = [{"City": city.name, "Radius (miles)": city.radius_miles} for city in c.cities]
            cities = st.data_editor(rows or [{"City": "", "Radius (miles)": 25}], num_rows="dynamic",
                                    width="stretch", key=f"fj_cities{suffix}",
                                    column_config={"Radius (miles)": st.column_config.NumberColumn(min_value=1,
                                                                                                   max_value=100)})
            low, high, posted = st.columns(3)
            salary_min = low.number_input("Minimum salary ($)", value=c.salary_min or 0, step=5000, min_value=0)
            salary_max = high.number_input("Maximum salary ($)", value=c.salary_max or 0, step=5000, min_value=0)
            max_days = posted.selectbox("Posted", list(DATE_OPTIONS), index=list(DATE_OPTIONS).index(c.max_days_old),
                                        format_func=DATE_OPTIONS.get)
            st.caption("Leave a salary at 0 for no limit. Only salaries stated in the posting are checked; postings "
                       "with no salary or only an Adzuna estimate are kept and labeled.")
            ex_companies = st.text_area("Skip these companies (optional)", value="\n".join(c.exclude_companies),
                                        height=70, placeholder="Staffing agencies, for example")
            ex_keywords = st.text_area("Skip postings with these words (optional)", value="\n".join(c.exclude_keywords),
                                       height=70)
            submitted = st.form_submit_button("Save search", type="primary")

        if submitted:
            criteria = SearchCriteria(
                titles=_lines(titles),
                cities=[City(str(r["City"]).strip(), int(r["Radius (miles)"] or 25))
                        for r in cities if r.get("City") and str(r["City"]).strip()],
                settings=list(picked or []),
                salary_min=int(salary_min) or None,
                salary_max=int(salary_max) or None,
                max_days_old=max_days,
                exclude_companies=_lines(ex_companies),
                exclude_keywords=_lines(ex_keywords),
            )
            problems = criteria.problems() + ([] if name.strip() else ["Give the search a name."])
            if problems:
                for problem in problems:
                    st.error(problem)
            else:
                store.save_search(name, criteria, current["id"] if current else None)
                st.session_state.fj_editing = False
                st.session_state.fj_flash = ("success", f"Saved “{name.strip()}”.")
                st.rerun()
        if current and st.button("Delete this search", key=f"fj_delete{suffix}"):
            store.delete_search(current["id"])
            st.session_state.fj_flash = ("success", f"Deleted “{current['name']}”.")
            st.rerun()


def _results() -> None:
    counts = store.count_jobs()
    top, toggle = st.columns([3, 2], vertical_alignment="center")
    with top:
        tab = st.segmented_control("Show", list(TABS), default="new", key="fj_tab",
                                   format_func=lambda s: f"{TABS[s]} ({counts[s]})", label_visibility="collapsed")
    hide = toggle.toggle("Hide jobs with no salary listed", key="fj_hide_no_salary")
    jobs = store.list_jobs(tab or "new", hide_no_salary=hide)

    with st.container(border=True, key="card_job_list"):
        widths = [0.5, 2.5, 1.4, 1.1, 0.9, 4.2]
        for col, label in zip(st.columns(widths), ["Fit", "Role", "Location", "Salary", "Posted", ""]):
            col.caption(label)
        if not jobs:
            st.caption("Nothing here yet." if (tab or "new") != "new" else
                       "No new postings. Run the search to look for more.")
        for job in jobs:
            fit, role, where, pay, when, actions = st.columns(widths, vertical_alignment="center")
            fit.markdown(fit_badge(job["fit"]), unsafe_allow_html=True)
            title = escape(job["title"] or "Untitled")
            if job["apply_url"]:
                title = f'<a href="{escape(job["apply_url"])}" target="_blank">{title}</a>'
            reason = f'  \n<span class="ja-muted">{escape(job["fit_reason"])}</span>' if job["fit_reason"] else ""
            role.markdown(f"**{title}**  \n"
                          f'<span class="ja-muted">{escape(job["company"] or "")} · {source_label(job["source"])}'
                          f'</span>{reason}',
                          unsafe_allow_html=True)
            setting = "Unknown: check posting" if job["work_setting"] == "unknown" else SETTING_LABELS[job["work_setting"]]
            where.markdown(f"{escape(job['location'] or 'Remote (US)')}  \n"
                           f'<span class="ja-muted">{setting}</span>', unsafe_allow_html=True)
            pay.markdown(salary_label(job).replace("$", r"\$"))  # two $ signs would render as math
            when.markdown(posted_label(job["posted_at"]))
            with actions, st.container(horizontal=True, gap="small"):
                status = job["status"]
                if status == "applying":
                    if st.button("Open letter", key=f"fj_open_{job['id']}", type="primary"):
                        _start_letter(job)
                elif status in ("new", "saved") and st.button("Start letter", key=f"fj_letter_{job['id']}",
                                                              type="primary"):
                    _start_letter(job)
                if status in ("new", "saved"):
                    with st.popover("More", key=f"fj_more_{job['id']}"):
                        if st.button("Fill without cover letter", key=f"fj_fill_{job['id']}"):
                            _fill_without_letter(job)
                if status == "new" and st.button("Save", key=f"fj_save_{job['id']}"):
                    store.set_status(job["id"], "saved")
                    st.rerun()
                if status in ("new", "saved") and st.button("Dismiss", key=f"fj_dismiss_{job['id']}"):
                    store.set_status(job["id"], "dismissed")
                    st.rerun()
                if status == "dismissed" and st.button("Move to New", key=f"fj_restore_{job['id']}"):
                    store.set_status(job["id"], "new")
                    st.rerun()
