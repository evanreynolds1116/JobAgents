"""Company watch list (Milestone 12): board links, the three public APIs (shapes taken from
real responses), title matching, the location rule and a run that includes the watch list."""

from datetime import datetime, timedelta

import httpx
import pytest

import config
from search import run, score, watchlist
from search.criteria import City, SearchCriteria
from search.normalize import guess_setting
from storage import db
from storage import jobs as store

NOW = datetime(2026, 10, 1, 9, 0, 0)
RECENT = (NOW - timedelta(days=1)).isoformat() + "-05:00"


@pytest.mark.parametrize("link, board", [
    ("https://job-boards.greenhouse.io/axios", watchlist.Board("greenhouse", "axios")),
    ("boards.greenhouse.io/Axios/jobs/8163030", watchlist.Board("greenhouse", "axios")),
    ("https://job-boards.greenhouse.io/embed/job_app?for=axios&token=7818788", watchlist.Board("greenhouse", "axios")),
    ("https://jobs.lever.co/palantir/6ed76ce8", watchlist.Board("lever", "palantir")),
    ("https://jobs.ashbyhq.com/realmalliance/49a2da18/application", watchlist.Board("ashby", "realmalliance")),
    ("https://careers.example.com/jobs", None),
    ("https://job-boards.greenhouse.io/embed/job_app", None),
])
def test_parse_board(link, board):
    assert watchlist.parse_board(link) == board


GREENHOUSE = {"jobs": [
    {"id": 1, "title": "Senior Software Engineer", "company_name": "Acme Health",
     "location": {"name": "Nashville, TN"}, "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/1",
     "first_published": RECENT, "updated_at": RECENT,
     "content": "&lt;p&gt;Hybrid, three days a week in our Nashville office. Python and SQL.&lt;/p&gt;"},
    {"id": 2, "title": "Software Engineer", "company_name": "Acme Health", "location": {"name": "London, UK"},
     "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/2", "first_published": RECENT,
     "content": "&lt;p&gt;In our London office five days a week.&lt;/p&gt;"},
    {"id": 3, "title": "Account Manager", "company_name": "Acme Health", "location": {"name": "Remote"},
     "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/3", "first_published": RECENT,
     "content": "&lt;p&gt;Sales.&lt;/p&gt;"},  # title doesn't match the search
]}
LEVER = [
    {"id": "a1", "text": "Backend Software Engineer", "hostedUrl": "https://jobs.lever.co/tilt/a1",
     "categories": {"location": "Remote - US", "allLocations": ["Remote - US"]}, "country": "US",
     "workplaceType": "remote", "createdAt": int((NOW - timedelta(days=2)).timestamp() * 1000),
     "descriptionPlain": "Build payment APIs.", "lists": [{"text": "Requirements", "content": "<li>Python</li>"}],
     "additionalPlain": "Benefits.", "salaryRange": {"min": 120000, "max": 150000, "currency": "USD",
                                                     "interval": "per-year-salary"}},
    {"id": "a2", "text": "Backend Engineer", "hostedUrl": "https://jobs.lever.co/tilt/a2",
     "categories": {"location": "London", "allLocations": ["London"]}, "country": "GB",
     "workplaceType": "remote", "createdAt": int(NOW.timestamp() * 1000), "descriptionPlain": "Remote in the UK."},
    {"id": "a3", "text": "Software Engineer", "hostedUrl": "https://jobs.lever.co/tilt/a3",
     "categories": {"location": "Remote - US"}, "country": "US", "workplaceType": "remote",
     "createdAt": int((NOW - timedelta(days=20)).timestamp() * 1000), "descriptionPlain": "Old posting."},
]
ASHBY = {"jobs": [
    {"id": "r1", "title": "Software Engineer - Backend", "location": "Knoxville, TN", "secondaryLocations": [],
     "workplaceType": "Hybrid", "isRemote": False, "publishedAt": RECENT, "jobUrl": "https://jobs.ashbyhq.com/realm/r1",
     "descriptionPlain": "Hybrid role in Knoxville.", "address": {"postalAddress": {"addressCountry": "United States"}},
     "compensation": {"summaryComponents": [{"compensationType": "Salary", "interval": "1 YEAR",
                                             "currencyCode": "USD", "minValue": 100000, "maxValue": 130000}]}},
]}


def board_handler(request: httpx.Request) -> httpx.Response:
    host, path = request.url.host, request.url.path
    if host == "api.adzuna.com":
        return httpx.Response(200, json={"results": []})
    if host == "boards-api.greenhouse.io":
        return httpx.Response(200, json=GREENHOUSE) if "/acme/" in path else httpx.Response(404)
    if host == "api.lever.co":
        return httpx.Response(200, json=LEVER)
    if host == "api.ashbyhq.com":
        return httpx.Response(200, json=ASHBY)
    raise AssertionError(f"unexpected request to {request.url}")


def client():
    return httpx.Client(transport=httpx.MockTransport(board_handler))


def test_greenhouse_job():
    job = watchlist.to_job("greenhouse", GREENHOUSE["jobs"][0], "Acme")
    assert (job.source, job.source_id, job.company, job.location) == ("greenhouse", "1", "Acme Health", "Nashville, TN")
    assert job.description.startswith("Hybrid, three days") and "<p>" not in job.description
    assert job.work_setting == "hybrid" and job.extra["board_setting"] is None
    assert job.posted_at and job.apply_url.endswith("/jobs/1")


def test_lever_job():
    job = watchlist.to_job("lever", LEVER[0], "Tilt")
    assert job.title == "Backend Software Engineer" and job.company == "Tilt"
    assert job.work_setting == "remote" and job.extra["board_setting"] == "remote" and job.extra["country"] == "US"
    assert (job.salary_min, job.salary_max, job.salary_estimated) == (120000.0, 150000.0, False)
    assert "Requirements\n- Python" in job.description and job.description.endswith("Benefits.")


def test_ashby_job():
    job = watchlist.to_job("ashby", ASHBY["jobs"][0], "Realm")
    assert job.work_setting == "hybrid" and job.extra["country"] == "United States"
    assert (job.salary_min, job.salary_max) == (100000.0, 130000.0)
    assert job.extra["locations"] == ["Knoxville, TN"]


@pytest.mark.parametrize("job_title, match", [
    ("Senior Backend Engineer", "Backend Engineer"),
    ("Senior Backend Software Engineer", "Software Engineer"),  # both match; the first title wins
    ("Software Engineer - Backend", "Software Engineer"),
    ("Account Manager", None),
    ("Engineering Manager", None),
])
def test_matching_title(job_title, match):
    assert watchlist.matching_title(job_title, ["Software Engineer", "Backend Engineer"]) == match


@pytest.mark.parametrize("location, near", [
    ("Nashville, TN", "Nashville, TN"),
    ("Remote; Charlotte, NC preferred", "Charlotte, NC"),
    ("San Francisco, California, United States", "San Francisco, CA"),
    ("Hybrid - Knoxville, Tennessee", "Knoxville, TN"),
])
def test_coordinates(location, near):
    from search import places

    assert watchlist.coordinates(location) == places.lookup(near)


def test_coordinates_unknown():
    assert watchlist.coordinates("London") is None and watchlist.coordinates("Remote") is None


def criteria(**overrides) -> SearchCriteria:
    base = dict(titles=["Software Engineer", "Backend Engineer"],
                cities=[City("Nashville, TN", 25), City("Knoxville, TN", 25)],
                settings=["remote", "hybrid"], max_days_old=3)
    base.update(overrides)
    return SearchCriteria(**base)


def test_contexts_for():
    nashville = watchlist.to_job("greenhouse", GREENHOUSE["jobs"][0], "Acme")
    kinds = [(q.kind, q.city) for q in watchlist.contexts_for(nashville, "Software Engineer", criteria())]
    assert kinds == [("remote", None), ("city", "Nashville, TN")]
    uk = watchlist.to_job("lever", LEVER[1], "Tilt")
    assert watchlist.contexts_for(uk, "Backend Engineer", criteria()) == []  # not US, not near a city
    assert [q.kind for q in watchlist.contexts_for(nashville, "x", criteria(settings=["remote"]))] == ["remote"]


@pytest.fixture
def ready(app_paths, monkeypatch):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n"
                               "ADZUNA_APP_ID=test-id\nADZUNA_APP_KEY=test-key\n")
    db.init_db()
    asked = []

    def fake_scorer(jobs):
        asked.append([j.source_id for j in jobs])
        # Pretend Claude reads everything as on-site, to show that a board's own label wins.
        return [score.Score("onsite" if j.source == "lever" else guess_setting(j.title, j.description), 4, "ok")
                for j in jobs], []

    monkeypatch.setattr(score, "score_jobs", fake_scorer)
    return asked


def saved(c: SearchCriteria) -> dict:
    search_id = store.save_search("Engineering", c)
    return next(s for s in store.list_searches() if s["id"] == search_id)


def test_run_includes_the_watch_list(ready):
    store.add_company("Acme Health", "greenhouse", "acme")
    store.add_company("Tilt", "lever", "tilt")
    store.add_company("Realm", "ashby", "realm")
    store.add_company("Gone Co", "greenhouse", "gone")  # board no longer exists
    result = run.run_searches([saved(criteria())], client=client(), now=NOW)

    kept = {j["source_id"]: j for j in store.list_jobs("new")}
    assert set(kept) == {"1", "a1", "a3", "r1"}  # a3 was posted 20 days ago: still open, so kept
    assert kept["a1"]["work_setting"] == "remote"  # Lever says remote, so Claude's "onsite" doesn't override it
    assert kept["1"]["work_setting"] == "hybrid" and kept["1"]["source"] == "greenhouse"
    assert kept["r1"]["salary_min"] == 100000 and kept["1"]["fit"] == 4
    assert result.companies == 4 and result.calls == 6
    assert result.dropped == {"outside your cities": 1,                    # a2: remote in the UK
                              "not remote and outside your cities": 1}     # 2: on-site in London
    assert result.errors == ["Gone Co (Greenhouse): no job board found. Check the careers link."]
    assert "4 watch-list companies" in result.summary()
    assert set(ready[0]) == {"1", "2", "a1", "a3", "r1"}  # Account Manager never matched, so it isn't scored


def test_watch_list_job_seen_again_is_not_new(ready):
    store.add_company("Tilt", "lever", "tilt")
    search = saved(criteria())
    run.run_searches([search], client=client(), now=NOW)
    again = run.run_searches([search], client=client(), now=NOW)
    assert again.new == 0 and again.duplicates >= 1 and ready[1] == []


def test_company_storage(app_paths):
    db.init_db()
    first = store.add_company("Axios", "greenhouse", "axios")
    assert store.add_company("Axios Media", "greenhouse", "axios") == first  # same board: renamed, not doubled
    store.add_company("Realm", "ashby", "realm")
    assert [c["name"] for c in store.list_companies()] == ["Axios Media", "Realm"]
    store.delete_company(first)
    assert [c["name"] for c in store.list_companies()] == ["Realm"]


def test_duplicate_is_judged_on_its_own_copy(ready):
    # Two Tilt "Backend Engineer" postings, both remote, share a duplicate key. The UK one
    # comes first and doesn't qualify; the US one does, and it's the one stored.
    us = dict(LEVER[1], id="a9", country="US", categories={"location": "Remote - US"}, descriptionPlain="US remote.")
    LEVER.append(us)
    try:
        store.add_company("Tilt", "lever", "tilt")
        result = run.run_searches([saved(criteria())], client=client(), now=NOW)
    finally:
        LEVER.remove(us)
    kept = {j["source_id"]: j for j in store.list_jobs("new")}
    assert "a9" in kept and "a2" not in kept and kept["a9"]["description"] == "US remote."
    assert result.duplicates == 1
