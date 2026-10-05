"""Job search (Milestone 10) against made-up Adzuna responses shaped like the real API."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

import config
from search import adzuna, normalize, places, run
from search.criteria import City, SearchCriteria
from storage import db
from storage import jobs as store

NOW = datetime(2026, 10, 1, 9, 0, 0)


def ad(id_, title, company, location, description="", days_old=0.5, salary=None, predicted=False,
       coords=(36.16, -86.78)):
    # Adzuna sends UTC times ending in Z.
    created = (NOW - timedelta(days=days_old)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    item = {"id": id_, "title": title, "company": {"display_name": company},
            "location": {"display_name": location, "area": ["US"]}, "description": description,
            "created": created, "redirect_url": f"https://www.adzuna.com/land/ad/{id_}",
            "contract_time": "full_time"}
    if coords:
        item.update(latitude=coords[0], longitude=coords[1])
    if salary:
        item.update(salary_min=salary[0], salary_max=salary[1], salary_is_predicted="1" if predicted else "0")
    return item


# What each (title, place) query returns. "remote" is the nationwide remote query.
RESPONSES = {
    ("Software Engineer", "Nashville, TN"): [
        ad("101", "Software Engineer", "Acme Health, Inc.", "Nashville, Davidson County",
           "Hybrid: three days a week in our Nashville office.", salary=(95000, 120000)),
        ad("102", "Software Engineer", "Riverbend Labs", "Nashville, Davidson County",
           "This role is on-site five days a week."),  # on-site wasn't picked
        ad("103", "Software Engineer", "Mystery Co", "Franklin, Williamson County",
           "Build APIs in Python.", days_old=2, coords=(35.925, -86.869)),  # setting unknown: kept and labeled
        ad("104", "Software Engineer", "Old Posting LLC", "Nashville, Davidson County",
           "Hybrid role.", days_old=6),  # older than 3 days
        ad("105", "Software Engineer", "Lowball Inc", "Nashville, Davidson County",
           "Hybrid.", salary=(40000, 50000)),  # below the salary range
        ad("106", "Software Engineer", "TalentStaff Agency", "Nashville, Davidson County",
           "Hybrid contract role."),  # excluded company
    ],
    ("Software Engineer", "Knoxville, TN"): [
        ad("201", "Software Engineer", "Regal Cinemas", "Knoxville, Knox County", "Hybrid team in Knoxville.",
           coords=(35.96, -83.92)),
        # Adzuna's distance filter let this one through: Morristown is about 40 miles away.
        ad("202", "AI Software Engineer", "Accenture", "Morristown, Hamblen County", "Build AI tools.",
           coords=(36.204, -83.300)),
        ad("203", "Software Engineer", "Pilot Co", "Knoxville, Knox County", "Hybrid in Knoxville.",
           coords=None),  # no coordinates: left to Adzuna's filter
    ],
    ("Software Engineer", "remote"): [
        ad("301", "Software Engineer", "OnePay", "Seattle, King County", "This is a fully remote role."),
        ad("302", "Software Engineer", "Chicago Data Co", "Chicago, Cook County",
           "Remote-friendly culture, but this role is hybrid in Chicago."),  # hybrid outside the cities
        ad("303", "Software Engineer", "Denver Robotics", "Denver, Denver County",
           "Not remote. On-site in Denver."),  # on-site outside the cities
    ],
    ("Backend Engineer", "Nashville, TN"): [
        # The same Acme job listed under another title and spelled differently: a duplicate.
        ad("101", "Software Engineer", "Acme Health, Inc.", "Nashville, Davidson County",
           "Hybrid: three days a week in our Nashville office.", salary=(95000, 120000)),
        ad("401", "Backend Engineer", "Tilt", "Nashville, Davidson County", "Hybrid, Nashville.",
           salary=(110000, 140000), predicted=True),
    ],
    ("Backend Engineer", "Knoxville, TN"): [],
    ("Backend Engineer", "remote"): [
        ad("501", "Backend Engineer", "Realm", "Austin, Travis County", "Remote (US)."),
        ad("999", "Software Engineer", "OnePay Inc.", "Seattle, King County",
           "This is a fully remote role."),  # same OnePay job, different ID: duplicate key
    ],
}


def criteria(**overrides) -> SearchCriteria:
    base = dict(titles=["Software Engineer", "Backend Engineer"],
                cities=[City("Nashville, TN", 25), City("Knoxville, TN", 25)],
                settings=["remote", "hybrid"], salary_min=60000, max_days_old=3,
                exclude_companies=["TalentStaff"])
    base.update(overrides)
    return SearchCriteria(**base)


class FakeAdzuna:
    def __init__(self, fail_on=None):
        self.requests = []
        self.fail_on = fail_on

    def handler(self, request: httpx.Request) -> httpx.Response:
        q = dict(request.url.params)
        self.requests.append(q)
        place = q.get("where") or "remote"
        if self.fail_on == place:
            return httpx.Response(401, json={"exception": "AUTH_FAIL"})
        return httpx.Response(200, json={"count": 99, "mean": 1, "results": RESPONSES[(q["title_only"], place)]})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


@pytest.fixture
def ready(app_paths):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n"
                               "ADZUNA_APP_ID=test-id\nADZUNA_APP_KEY=test-key\n")
    db.init_db()


def saved(c: SearchCriteria) -> dict:
    search_id = store.save_search("Engineering", c)
    return next(s for s in store.list_searches() if s["id"] == search_id)


# --- Acceptance scenario -----------------------------------------------------------


def test_two_titles_two_cities_last_three_days(ready):
    fake = FakeAdzuna()
    result = run.run_searches([saved(criteria())], client=fake.client(), now=NOW)

    assert result.calls == 6 == len(fake.requests)  # 2 titles x (2 cities + 1 remote)
    kept = {j["source_id"]: j for j in store.list_jobs("new")}
    assert set(kept) == {"101", "103", "201", "203", "301", "401", "501"}
    keys = [j["dedupe_key"] for j in kept.values()]
    assert len(keys) == len(set(keys))  # no duplicates
    assert result.duplicates == 2  # Acme listed twice, OnePay under two IDs
    assert result.dropped == {
        "in a work setting you didn't pick": 1,           # 102 on-site in Nashville
        "older than your date range": 1,                   # 104
        "outside your salary range": 1,                    # 105
        "from excluded companies": 1,                      # 106
        "not remote and outside your cities": 2,           # 302 hybrid in Chicago, 303 on-site in Denver
        "outside your cities' radius": 1,                  # 202 in Morristown, 40 miles from Knoxville
    }
    assert kept["301"]["work_setting"] == "remote" and kept["301"]["location"].startswith("Seattle")
    assert kept["501"]["work_setting"] == "remote"
    assert kept["103"]["work_setting"] == "unknown"
    assert kept["401"]["salary_estimated"] == 1
    assert store.calls_today("adzuna") == 6
    assert store.list_searches()[0]["last_run_at"] == NOW.isoformat()


def test_query_parameters_follow_adzuna_spec(ready):
    fake = FakeAdzuna()
    run.run_searches([saved(criteria(salary_max=150000))], client=fake.client(), now=NOW)
    city = next(r for r in fake.requests if r.get("where") == "Nashville, TN")
    assert city["title_only"] == "Software Engineer"
    assert city["distance"] == "40"  # 25 miles in kilometres
    assert city["max_days_old"] == "3" and city["sort_by"] == "date" and city["results_per_page"] == "50"
    assert city["salary_min"] == "60000" and city["salary_max"] == "150000"
    assert city["salary_include_unknown"] == "1"  # no-salary postings are kept and labeled
    assert city["app_id"] == "test-id" and city["app_key"] == "test-key"
    remote = next(r for r in fake.requests if "where" not in r)
    assert remote["what"] == "remote" and "distance" not in remote


def test_rerun_finds_nothing_new(ready):
    search = saved(criteria())
    run.run_searches([search], client=FakeAdzuna().client(), now=NOW)
    store.set_status(store.list_jobs("new")[0]["id"], "dismissed")
    again = run.run_searches([search], client=FakeAdzuna().client(), now=NOW)
    assert again.new == 0 and again.duplicates == 9
    assert store.count_jobs()["dismissed"] == 1  # a dismissed job isn't brought back as new


def test_date_filter_options(ready):
    fake = FakeAdzuna()
    run.run_searches([saved(criteria(max_days_old=1, salary_min=None))], client=fake.client(), now=NOW)
    assert {r["max_days_old"] for r in fake.requests} == {"1"}
    kept = {j["source_id"] for j in store.list_jobs("new")}
    assert "103" not in kept  # 2 days old
    assert "104" not in kept and "101" in kept


def test_remote_only_skips_city_queries(ready):
    fake = FakeAdzuna()
    run.run_searches([saved(criteria(settings=["remote"]))], client=fake.client(), now=NOW)
    assert len(fake.requests) == 2 and all("where" not in r for r in fake.requests)


def test_onsite_picked_keeps_onsite_jobs_in_cities(ready):
    run.run_searches([saved(criteria(settings=["hybrid", "onsite"]))], client=FakeAdzuna().client(), now=NOW)
    assert "102" in {j["source_id"] for j in store.list_jobs("new")}


# --- Allowance and errors ----------------------------------------------------------


def test_pauses_before_the_daily_limit(ready):
    store.record_calls("adzuna", run.DAILY_LIMIT - 3)
    fake = FakeAdzuna()
    with pytest.raises(run.UsageLimit, match="needs 6 Adzuna calls"):
        run.run_searches([saved(criteria())], client=fake.client(), now=NOW)
    assert fake.requests == []  # nothing called


def test_pauses_before_the_monthly_limit(ready, monkeypatch):
    monkeypatch.setattr(store, "calls_today", lambda service: 0)
    monkeypatch.setattr(store, "calls_this_month", lambda service: run.MONTHLY_LIMIT - 2)
    fake = FakeAdzuna()
    with pytest.raises(run.UsageLimit, match="this month"):
        run.run_searches([saved(criteria())], client=fake.client(), now=NOW)
    assert fake.requests == []


def test_monthly_usage_adds_up_days(ready):
    from datetime import date

    store.record_calls("adzuna", 10, day=date(2026, 9, 2))
    store.record_calls("adzuna", 5, day=date(2026, 9, 30))
    store.record_calls("adzuna", 7, day=date(2026, 10, 1))
    assert store.calls_this_month("adzuna", day=date(2026, 9, 15)) == 15
    assert store.calls_today("adzuna", day=date(2026, 10, 1)) == 7


def test_failed_query_is_reported_and_others_continue(ready):
    fake = FakeAdzuna(fail_on="Knoxville, TN")
    result = run.run_searches([saved(criteria())], client=fake.client(), now=NOW)
    assert len(result.errors) == 2 and "rejected the app ID or key" in result.errors[0]
    assert result.new == 5  # everything except Regal in Knoxville
    assert store.calls_today("adzuna") == 6  # failed calls still count


def test_needs_adzuna_keys(app_paths):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=sk-ant-test-0000000000000000\n")
    db.init_db()
    with pytest.raises(adzuna.AdzunaError, match="ADZUNA_APP_ID"):
        run.run_searches([saved(criteria())], client=FakeAdzuna().client(), now=NOW)


# --- Pieces --------------------------------------------------------------------------


def test_query_builder_sizing_example():
    # Spec: 3 titles x (2 cities + 1 nationwide remote search) is 9 calls.
    c = criteria(titles=["A", "B", "C"])
    queries = adzuna.build_queries(c)
    assert len(queries) == 9
    assert [q.kind for q in queries[:3]] == ["city", "city", "remote"]


@pytest.mark.parametrize("text, setting", [
    ("Fully remote role in the US", "remote"),
    ("Work from home anywhere", "remote"),
    ("Hybrid, 2 days in office", "hybrid"),
    ("Remote-friendly but hybrid in Chicago", "hybrid"),
    ("This is not remote; on-site in Denver", "onsite"),
    ("In-office five days a week", "onsite"),
    ("Build APIs in Python", "unknown"),
])
def test_guess_setting(text, setting):
    assert normalize.guess_setting(text) == setting


def test_dedupe_key_ignores_spelling():
    a = normalize.dedupe_key("Acme Health, Inc.", "Software Engineer", "Nashville, Davidson County")
    b = normalize.dedupe_key("ACME HEALTH", "Software  Engineer", "Nashville")
    assert a == b == "acme health | software engineer | nashville"


@pytest.mark.parametrize("job, label", [
    ({"salary_min": 60000, "salary_max": 75000}, "$60k–$75k"),
    ({"salary_min": 55000, "salary_max": 62000, "salary_estimated": 1}, "$55k–$62k est."),
    ({"salary_min": 70000, "salary_max": 70000}, "$70k"),
    ({"salary_min": None, "salary_max": None}, "Not listed"),
])
def test_salary_label(job, label):
    assert normalize.salary_label(job) == label


def test_criteria_round_trip_and_checks():
    c = criteria()
    assert SearchCriteria.from_dict(c.to_dict()) == c
    assert c.problems() == []
    assert "Add at least one job title." in SearchCriteria(titles=[" "]).problems()
    assert "Hybrid and on-site jobs need at least one city." in SearchCriteria(titles=["A"], settings=["hybrid"]).problems()
    rows = dict(c.summary())
    assert rows["Remote"] == "Anywhere in the US" and rows["Posted"] == "Last 3 days"
    assert rows["Hybrid"] == "near Nashville, TN (25 mi); Knoxville, TN (25 mi)"


def test_city_lookup_and_distance():
    assert places.lookup("Nashville, TN") == places.lookup("nashville, tennessee") is not None
    assert places.lookup("Saint Louis, MO") == places.lookup("St. Louis, MO") is not None
    assert places.lookup("Ventura, CA") and places.lookup("Louisville, KY") and places.lookup("Washington, DC")
    assert places.lookup("Nashville") is None and places.lookup("Nowhere, TN") is None
    knoxville, morristown = places.lookup("Knoxville, TN"), places.lookup("Morristown, TN")
    assert 39 < places.miles_between(knoxville, morristown) < 41


def test_radius_check_skips_remote_jobs_and_unknown_cities():
    far = adzuna.to_job(ad("1", "Engineer", "Far Co", "Seattle, King County", "Hybrid.", coords=(47.6, -122.3)))
    near = adzuna.to_job(ad("2", "Engineer", "Near Co", "Nashville, Davidson County", "Hybrid."))
    query = adzuna.Query("city", "Engineer", "Nashville, TN", 40, 25)
    assert run.outside_radius(far, query) and not run.outside_radius(near, query)
    assert not run.outside_radius(far, adzuna.Query("city", "Engineer", "Atlantis, ZZ", 40, 25))
    remote = adzuna.to_job(ad("3", "Engineer", "Remote Co", "Seattle, King County", "Fully remote.",
                              coords=(47.6, -122.3)))
    assert run.keep(remote, query, criteria(), NOW) is None


def test_unknown_city_is_reported():
    c = criteria(cities=[City("Nashvile, TN", 25)])
    assert any("Couldn't find \"Nashvile, TN\"" in p for p in c.problems())
