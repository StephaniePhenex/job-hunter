"""Shared Playwright helpers (sync API wrapped by scrapers)."""

from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from app.core.config import get_settings


def _new_page(browser: Browser) -> tuple[Page, object]:
    """Create a new page + context from an existing browser. Caller must close context."""
    settings = get_settings()
    context = browser.new_context(
        user_agent=settings.playwright_user_agent,
        viewport={"width": 1280, "height": 720},
    )
    page = context.new_page()
    page.set_default_timeout(settings.playwright_timeout_ms)
    return page, context


@contextmanager
def playwright_session() -> Iterator[Browser]:
    """Launch one Chromium browser for a whole pipeline run.

    Use this when multiple scrapers share one process to avoid spawning
    a separate Chromium instance per scraper.
    """
    with sync_playwright() as p:  # type: ignore[assignment]
        pw: Playwright = p
        browser: Browser = pw.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@contextmanager
def browser_page(browser: Browser) -> Iterator[Page]:
    """Create a page from an *existing* browser (shared session)."""
    page, context = _new_page(browser)
    try:
        yield page
    finally:
        context.close()  # type: ignore[attr-defined]


@contextmanager
def playwright_page() -> Iterator[Page]:
    """Standalone page with its own browser (kept for standalone scraper use)."""
    with playwright_session() as browser:
        with browser_page(browser) as page:
            yield page
