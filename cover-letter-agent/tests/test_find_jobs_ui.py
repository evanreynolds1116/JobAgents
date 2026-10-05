"""Find jobs screen with Adzuna faked."""

from datetime import datetime, timedelta

import pytest
from streamlit.testing.v1 import AppTest

import config
from search import adzuna, run
from search.criteria import City, SearchCriteria
from search.normalize import Job
from storage import db
from storage import jobs as store
from ui.find_jobs import posted_label

SCRIPT = "from ui import find_jobs\nfind_jobs.find_jobs_page()\n"


@pytest.fixture
def keys(app_paths):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n"
                               "ADZUNA_APP_ID=test-id\nADZUNA_APP_KEY=test-key\n")
    db.init_db()


def open_page():
    at = AppTest.from_string(SCRIPT, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def click(at, label, nth=0):
    [b for b in at.button if b.label == label][nth].click().run()
    assert not at.exception, at.exception


def text(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def add_job(source_id, title, company, setting="hybrid", salary=(None, None), estimated=False, days_old=0):
    posted = (datetime.now() - timedelta(days=days_old)).isoformat(timespec="seconds")
    job = Job("adzuna", source_id, title, company, "Nashville, Davidson County", setting, salary[0], salary[1],
              estimated, posted, f"https://www.adzuna.com/land/ad/{source_id}", "")
    store.upsert(job, None, datetime.now().isoformat(timespec="seconds"))


def save_search():
    return store.save_search("Engineering", SearchCriteria(
        titles=["Software Engineer"], cities=[City("Nashville, TN", 25)], settings=["remote", "hybrid"],
        salary_min=60000, max_days_old=3))


def test_without_keys_explains_setup_and_still_lets_you_save(app_paths):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n")
    db.init_db()
    at = open_page()
    assert "Add your Adzuna keys to search." in at.info[0].value
    assert "Set up a search" in [s.value for s in at.subheader]
    assert next(b for b in at.button if b.label == "Run search now").disabled


def test_saving_a_search_through_the_form(keys):
    at = open_page()
    at.text_input[0].input("Engineering")
    at.text_area[0].input("Software Engineer\nBackend Engineer")
    click(at, "Save search")
    assert "Hybrid and on-site jobs need at least one city." in [e.value for e in at.error]  # hybrid is a default
    at.button_group[0].set_value(["remote"])
    click(at, "Save search")
    (saved,) = store.list_searches()
    assert saved["name"] == "Engineering"
    assert saved["criteria"].titles == ["Software Engineer", "Backend Engineer"]
    assert saved["criteria"].settings == ["remote"]


def test_form_reports_problems(keys):
    at = open_page()
    at.text_area[0].input("Software Engineer")
    click(at, "Save search")
    assert "Give the search a name." in [e.value for e in at.error]
    assert store.list_searches() == []


def test_search_card_and_results(keys):
    save_search()
    store.record_calls("adzuna", 6)
    add_job("1", "Software Engineer", "Acme Health", salary=(95000, 120000))
    add_job("2", "Backend Engineer", "Tilt", salary=(110000, 140000), estimated=True, days_old=1)
    add_job("3", "Platform Engineer", "Mystery Co", setting="unknown", days_old=2)
    at = open_page()
    page = text(at)
    assert "Saved search: Engineering" in [s.value for s in at.subheader]
    assert any("Adzuna calls today: 6 of 250 · this search uses 2" in c.value for c in at.caption)
    for expected in ("Anywhere in the US", "near Nashville, TN (25 mi)", "&#36;60k–any", "Last 3 days",
                     "Software Engineer</a>**", "Acme Health · via Adzuna", r"\$95k–\$120k", r"\$110k–\$140k est.",
                     "Not listed", "Unknown: check posting", "Today", "1 day ago", "2 days ago"):
        assert expected in page, expected
    assert at.segmented_control(key="fj_tab").options == ["New (3)", "Saved (0)", "Dismissed (0)"]
    at.toggle(key="fj_hide_no_salary").set_value(True).run()
    assert "Mystery Co" not in text(at)


def test_save_dismiss_and_restore(keys):
    save_search()
    add_job("1", "Software Engineer", "Acme Health")
    add_job("2", "Backend Engineer", "Tilt")
    at = open_page()
    click(at, "Save")
    click(at, "Dismiss")
    assert store.count_jobs() == {"new": 0, "saved": 1, "dismissed": 1, "applying": 0}
    at.segmented_control(key="fj_tab").set_value("dismissed").run()
    click(at, "Move to New")
    assert store.count_jobs()["new"] == 1


def test_run_now_shows_summary(keys, monkeypatch):
    save_search()

    def fake_run(searches):
        result = run.RunResult(calls=2, fetched=40, new=12, duplicates=5)
        result.dropped["not remote and outside your cities"] = 3
        result.errors = ["Software Engineer near Nashville, TN: Adzuna took too long to respond."]
        return result

    monkeypatch.setattr(run, "run_searches", fake_run)
    at = open_page()
    click(at, "Run search now")
    assert at.success[0].value == ("2 Adzuna calls: 12 new jobs, 40 found, 5 already seen, "
                                   "3 not remote and outside your cities.")
    assert "took too long" in at.warning[0].value


@pytest.mark.parametrize("error", [run.UsageLimit("This run needs 2 Adzuna calls and 249 of today's 250 are used."),
                                   adzuna.AdzunaError("Adzuna rejected the app ID or key in .env.")])
def test_run_now_errors(keys, monkeypatch, error):
    save_search()

    def fail(searches):
        raise error

    monkeypatch.setattr(run, "run_searches", fail)
    at = open_page()
    click(at, "Run search now")
    assert str(error) == at.error[0].value


def test_posted_label():
    now = datetime(2026, 10, 1, 9, 0)
    assert posted_label("2026-10-01T07:00:00", now) == "Today"
    assert posted_label("2026-09-30T23:00:00", now) == "1 day ago"
    assert posted_label("2026-09-27T12:00:00", now) == "4 days ago"
    assert posted_label(None, now) == "Date not given"


def test_last_run_label():
    from ui.find_jobs import last_run_label

    now = datetime.now()
    assert last_run_label(None) == "never"
    assert last_run_label(now.replace(hour=7, minute=52).isoformat()) == "today at 7:52 AM"
    assert last_run_label((now - timedelta(days=1)).isoformat()) == "yesterday"
