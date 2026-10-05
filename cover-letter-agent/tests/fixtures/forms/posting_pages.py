"""Made-up pages for link-resolution tests, served by a Playwright route instead of the
internet: an Adzuna redirect, an employer's posting with an Apply link, an aggregator
listing, a page embedding a Greenhouse form, and a page asking you to log in."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
GREENHOUSE_FORM = "https://job-boards.greenhouse.io/acme/jobs/1"
LEVER_POSTING = "https://jobs.lever.co/tilt/abc"
LEVER_FORM = "https://jobs.lever.co/tilt/abc/apply"


def page(body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'></head><body>{body}</body></html>"


ASHBY_FORM = "https://jobs.ashbyhq.com/onepay/123/application"
NO_PREVENT = page(  # a typeless button whose page forgot to stop the default: it would submit
    "<form onsubmit='window.__submitted = true; return false;'><label for='n'>Name</label><input id='n'>"
    "<label for='e'>Email</label><input id='e' type='email'><label for='p'>Phone</label><input id='p'>"
    "<button id='plain'>Yes</button></form>")

PAGES = {
    ASHBY_FORM: (HERE / "ashby_like.html").read_text(encoding="utf-8"),
    "https://careers.acme.example/no-prevent": NO_PREVENT,
    GREENHOUSE_FORM: (HERE / "greenhouse_like.html").read_text(encoding="utf-8"),
    LEVER_FORM: (HERE / "lever_like.html").read_text(encoding="utf-8"),
    LEVER_POSTING: page("<h1>Backend Engineer</h1><p>Build payment APIs.</p>"
                        f"<a class='postings-btn' href='{LEVER_FORM}'>Apply for this job</a>"),
    "https://careers.acme.example/jobs/1": page(
        "<h1>Software Engineer</h1><p>Join Acme Health.</p>"
        "<button type='submit'>Apply</button>"  # a button, never clicked
        f"<a href='{GREENHOUSE_FORM}'>Apply now</a><a href='https://careers.acme.example/benefits'>Benefits</a>"),
    "https://careers.acme.example/embedded": page(
        "<h1>Software Engineer</h1>"
        "<iframe id='grnhse_iframe' src='https://job-boards.greenhouse.io/embed/job_app?for=acme&token=1'></iframe>"),
    "https://job-boards.greenhouse.io/embed/job_app?for=acme&token=1":
        (HERE / "greenhouse_like.html").read_text(encoding="utf-8"),
    "https://www.adzuna.com/details/42": page(
        "<h1>Software Engineer</h1><a href='https://www.adzuna.com/'>Home</a>"
        "<a href='https://careers.acme.example/jobs/1'>Apply on company site</a>"),
    "https://www.adzuna.com/details/43": page("<h1>Software Engineer</h1><p>Sign in to see more.</p>"),
    "https://careers.acme.example/login-wall": page(
        "<h1>Sign in to apply</h1><form><label for='e'>Email</label><input id='e' type='email'>"
        "<label for='p'>Password</label><input id='p' type='password'><label for='n'>Name</label>"
        "<input id='n'><button type='submit'>Sign in</button></form>"),
}
REFUSED = {"https://www.adzuna.com/land/ad/9"}  # Adzuna turns automated browsers away like this
REDIRECTS = {
    "https://www.adzuna.com/land/ad/1": "https://careers.acme.example/jobs/1",
    "https://www.adzuna.com/land/ad/2": "https://www.linkedin.com/jobs/view/123",
    "https://www.adzuna.com/land/ad/3": "https://www.adzuna.com/details/43",
}


def serve(context, requested: list[str] | None = None) -> None:
    """Answer every request from the pages above; anything else is a 404. Redirects are
    page redirects: Playwright doesn't route the target of a server redirect it fulfilled."""
    def handler(route):
        url = route.request.url
        if requested is not None:
            requested.append(url)
        if url in REFUSED:
            route.fulfill(status=403, content_type="text/html", body=page("<h1>Access Denied</h1>"))
        elif url in REDIRECTS:
            route.fulfill(status=200, content_type="text/html",
                          body=page(f"<meta http-equiv='refresh' content='0;url={REDIRECTS[url]}'>Redirecting…"))
        elif url in PAGES:
            route.fulfill(status=200, content_type="text/html; charset=utf-8", body=PAGES[url])
        else:
            route.fulfill(status=404, body="not found")
    context.route("**/*", handler)
