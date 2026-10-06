from pathlib import Path

import httpx
import pytest

from agent import fetch

POSTINGS = Path(__file__).resolve().parent / "fixtures" / "postings"


def html(name):
    return (POSTINGS / name).read_text(encoding="utf-8")


def test_structured_job_data_wins_even_on_a_javascript_page():
    result = fetch.extract(html("jsonld_greenhouse_style.html"), "https://boards.example.com/x")
    assert result.ok
    assert result.hints == {"title": "Social Media Coordinator", "company": "Summit City Hockey Club"}
    assert result.text.startswith("Job title: Social Media Coordinator\nCompany: Summit City Hockey Club")
    assert "- Experience shooting and editing short-form video" in result.text
    assert "&lt;" not in result.text and "<li>" not in result.text


def test_plain_page_drops_navigation_and_footer():
    result = fetch.extract(html("plain_company_page.html"))
    assert result.ok
    assert "Marketing Coordinator" in result.text
    assert "2+ years in a marketing coordinator or similar role" in result.text
    assert "Privacy · Terms" not in result.text


@pytest.mark.parametrize("name, reason", [
    ("login_wall.html", "needs a login"),
    ("js_shell.html", "JavaScript"),
])
def test_unreadable_pages_fall_back_to_paste(name, reason):
    result = fetch.extract(html(name))
    assert not result.ok
    assert reason in result.reason


def test_unsupported_browser_page_counts_as_javascript():
    page = "<html><body><p>You are using an unsupported browser.</p><p>Download Chrome</p></body></html>"
    assert "JavaScript" in fetch.extract(page).reason


def test_long_posting_is_trimmed_with_warning():
    body = "".join(f"<p>Paragraph {i}: " + f"requirement {i} detail, " * 40 + "</p>\n" for i in range(60))
    result = fetch.extract(f"<html><body><main><h1>Job</h1>{body}</main></body></html>")
    assert result.ok and result.trimmed
    assert len(result.text) <= fetch.MAX_CHARS
    text, trimmed = fetch.trim("x" * (fetch.MAX_CHARS + 10))
    assert trimmed and len(text) <= fetch.MAX_CHARS
    assert fetch.trim("short") == ("short", False)


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_fetch_follows_redirects_and_reads_page():
    def handler(request):
        if request.url.path == "/go":
            return httpx.Response(302, headers={"location": "https://careers.example.com/job/1"})
        return httpx.Response(200, html=html("plain_company_page.html"))

    result = fetch.fetch("careers.example.com/go", client=client_for(handler))
    assert result.ok
    assert result.url == "https://careers.example.com/job/1"


@pytest.mark.parametrize("status, words", [
    (404, "expired"), (410, "expired"), (403, "blocked"), (429, "blocked"), (500, "HTTP 500"),
])
def test_fetch_http_errors(status, words):
    result = fetch.fetch("https://careers.example.com/job", client=client_for(lambda r: httpx.Response(status)))
    assert not result.ok and words in result.reason


def test_fetch_non_html_and_network_errors():
    pdf = client_for(lambda r: httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"}))
    assert "isn't a web page" in fetch.fetch("https://x.example/job.pdf", client=pdf).reason

    def boom(request):
        raise httpx.ConnectError("no route")

    assert "Couldn't connect" in fetch.fetch("https://x.example/job", client=client_for(boom)).reason

    def slow(request):
        raise httpx.ReadTimeout("slow")

    assert "too long" in fetch.fetch("https://x.example/job", client=client_for(slow)).reason


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/123",
    "https://www.indeed.com/viewjob?jk=abc",
    "linkedin.com/jobs/view/123",
])
def test_sites_that_forbid_automated_reading_are_not_requested(url):
    def handler(request):
        raise AssertionError("should not be requested")

    result = fetch.fetch(url, client=client_for(handler))
    assert not result.ok and "doesn't allow automated reading" in result.reason


def test_rejects_non_web_addresses():
    assert not fetch.fetch("ftp://example.com/job").ok
    assert not fetch.fetch("   ").ok


def test_redirect_to_a_no_fetch_site_stops_before_requesting_it():
    requested = []

    def handler(request):
        requested.append(request.url.host)
        return httpx.Response(302, headers={"location": "https://www.indeed.com/viewjob?jk=1"})

    result = fetch.fetch("https://aggregator.example.com/land/ad/1", client=client_for(handler))
    assert not result.ok and "leads to indeed.com" in result.reason
    assert requested == ["aggregator.example.com"]  # Indeed itself was never requested


def test_endless_redirects_give_up():
    loop = lambda r: httpx.Response(302, headers={"location": "/again"})  # noqa: E731
    result = fetch.fetch("https://careers.example.com/start", client=client_for(loop))
    assert not result.ok and "redirects too many times" in result.reason


@pytest.mark.parametrize("url, company", [
    ("https://job-boards.greenhouse.io/acmehealth/jobs/123", "Acmehealth"),
    ("https://boards.greenhouse.io/embed/job_app?for=acme&token=1", "Acme"),
    ("jobs.lever.co/acme-health/abc", "Acme Health"),
    ("https://jobs.ashbyhq.com/OnePay/123", "OnePay"),
    ("https://acme.wd5.myworkdayjobs.com/en-US/External/job/1", "Acme"),
    ("https://careers-acme.icims.com/jobs/1/job", "Acme"),
    ("https://careers.acme.com/jobs/123", "Acme"),
    ("https://www.acme.co.uk/careers/engineer", "Acme"),
    ("https://jobs.harpeth-health.org/123", "Harpeth Health"),
    ("https://www.adzuna.com/land/ad/123", None),
    ("https://www.linkedin.com/jobs/view/123", None),
    ("", None),
])
def test_company_from_url(url, company):
    assert fetch.company_from_url(url) == company


# --- Greenhouse careers pages ------------------------------------------------------

SHELL = "<html><body><nav>Log in</nav><div id='app'></div></body></html>"
GREENHOUSE_JOB = {
    "title": "Software Engineer, Core Platform", "company_name": "Acme",
    "absolute_url": "https://acme.io/job-detail/?gh_jid=6143413004",
    "location": {"name": "Remote - United States"},
    # The API sends the description HTML-escaped.
    "content": "&lt;p&gt;You'll build the platform our customers run on.&lt;/p&gt;&lt;ul&gt;"
               + "".join(f"&lt;li&gt;Requirement {i}: years of distributed systems work&lt;/li&gt;" for i in range(12))
               + "&lt;/ul&gt;",
}


def greenhouse_client(job=GREENHOUSE_JOB, page=SHELL):
    requested = []

    def handler(request):
        requested.append(str(request.url))
        if request.url.host == "boards-api.greenhouse.io":
            if request.url.path == "/v1/boards/acme/jobs/6143413004" and job is not None:
                return httpx.Response(200, json=job)
            return httpx.Response(404, json={"status": 404})
        return httpx.Response(200, html=page)

    return client_for(handler), requested


@pytest.mark.parametrize("url, found", [
    ("https://cribl.io/job-detail/6143413004", (["cribl"], "6143413004")),
    ("https://www.acme.com/careers/?gh_jid=123", (["acme"], "123")),
    ("https://careers.acme-health.com/jobs/4567890", (["acmehealth", "acme-health"], "4567890")),
    ("https://job-boards.greenhouse.io/acme/jobs/6143413004", (["acme"], "6143413004")),
    ("https://boards.greenhouse.io/embed/job_app?for=acme&token=55", (["acme"], "55")),
    ("https://careers.acme.com/jobs/123", None),          # a short number isn't taken for a job ID
    ("https://careers.acme.com/jobs/engineer", None),
    ("https://www.adzuna.com/details/6143413004", None),  # listing sites say nothing about the employer
])
def test_greenhouse_job_from_link(url, found):
    assert fetch.greenhouse_job(url) == found


def test_javascript_careers_page_is_read_from_greenhouse():
    client, requested = greenhouse_client()
    result = fetch.fetch("https://acme.io/job-detail/6143413004", client=client)
    assert result.ok
    assert result.hints == {"title": "Software Engineer, Core Platform", "company": "Acme"}
    assert result.text.startswith("Job title: Software Engineer, Core Platform\nCompany: Acme\n"
                                  "Location: Remote - United States\n\nYou'll build the platform")
    assert "- Requirement 11: years of distributed systems work" in result.text
    assert "&lt;" not in result.text and "<li>" not in result.text
    assert requested == ["https://acme.io/job-detail/6143413004",
                         "https://boards-api.greenhouse.io/v1/boards/acme/jobs/6143413004"]


def test_greenhouse_job_for_a_different_site_is_not_used():
    client, _ = greenhouse_client(job={**GREENHOUSE_JOB, "absolute_url": "https://other.example/jobs?gh_jid=1"})
    result = fetch.fetch("https://acme.io/job-detail/6143413004", client=client)
    assert not result.ok and "needs a login" in result.reason


def test_job_not_on_greenhouse_keeps_the_paste_fallback():
    client, requested = greenhouse_client(job=None)
    result = fetch.fetch("https://acme.io/job-detail/6143413004", client=client)
    assert not result.ok and len(requested) == 2


def test_readable_page_or_one_without_a_job_id_never_asks_greenhouse():
    client, requested = greenhouse_client(page=html("plain_company_page.html"))
    assert fetch.fetch("https://acme.io/job-detail/6143413004", client=client).ok
    client, requested_too = greenhouse_client()
    assert not fetch.fetch("https://acme.io/careers/engineer", client=client).ok
    assert len(requested) == 1 and len(requested_too) == 1
