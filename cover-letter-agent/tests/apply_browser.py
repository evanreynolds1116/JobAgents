"""Shared headless-Chrome fixtures for the application agent tests. Pages are served from
tests/fixtures/forms by a Playwright route, and the browser is offline, so nothing reaches
the internet. Skipped when Chrome isn't installed."""

import tempfile

import pytest

from tests.fixtures.forms import posting_pages


@pytest.fixture(scope="module")
def chrome(tmp_path_factory):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("Playwright isn't installed")
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                tempfile.mkdtemp(dir=tmp_path_factory.mktemp("chrome")), channel="chrome", headless=True)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Chrome couldn't start: {exc}")
        context.set_offline(True)
        posting_pages.serve(context)
        yield context
        context.close()


@pytest.fixture
def page(chrome):
    page = chrome.new_page()
    yield page
    page.close()


def open_form(page, url: str):
    page.goto(url)
    page.wait_for_load_state("domcontentloaded")
    return page
