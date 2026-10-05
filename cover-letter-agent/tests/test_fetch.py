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
