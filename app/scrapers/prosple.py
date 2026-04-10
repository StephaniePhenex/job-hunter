"""Prosple (Canada) — Playwright list page."""

import asyncio
import logging
import re

from playwright.sync_api import Browser

from app.core.config import get_settings
from app.utils.location_enrichment import enrich_jobs_location_from_detail_pages
from app.utils.playwright import browser_page, playwright_session
from app.utils.schemas import JobNormalized

logger = logging.getLogger(__name__)


def _location_from_listing_card(text: str) -> str:
    """Third+ lines on cards sometimes hold ``City, Province`` (before detail fetch)."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) < 3:
        return ""
    for line in lines[2:]:
        if "," not in line or not (5 <= len(line) <= 180):
            continue
        if re.search(r"(?i)\b(ON|BC|AB|QC|MB|SK|NS|NB|PE|NL|YT|NT|NU)\b", line):
            return line[:512]
        if re.search(r"(?i),\s*(Canada|United States|USA)\s*$", line):
            return line[:512]
    return ""


def _company_from_prosple_url(href: str) -> str:
    """Extract company name from URL slug: /graduate-employers/{slug}/jobs-internships/..."""
    m = re.search(r"/graduate-employers/([^/]+)/", href)
    if not m:
        return ""
    return m.group(1).replace("-", " ").title()


def _parse_anchor(a) -> JobNormalized | None:
    """Extract one normalized job from a Prosple listing anchor element."""
    href = a.get_attribute("href") or ""
    text = (a.inner_text() or "").strip()
    if not href or len(text) < 3:
        return None
    if href.startswith("/"):
        href = f"https://ca.prosple.com{href}"
    elif not href.startswith("http"):
        return None

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    title = lines[0][:512] if lines else ""
    # Card text no longer includes company name; extract from URL slug instead.
    company = _company_from_prosple_url(href)
    location = _location_from_listing_card(text) or "Canada"

    return JobNormalized(
        title=title,
        company=company,
        location=location,
        url=href,
        description=text[:2000],
        posted_at="",
        source="prosple",
    )


def _scrape_with_page(page) -> list[JobNormalized]:
    """Run the Prosple scrape against an already-open Playwright page."""
    settings = get_settings()
    url = str(settings.prosple_search_url)
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    # Listing links use /graduate-employers/.../jobs-internships/... (not legacy /job/)
    anchors = page.query_selector_all(
        "a[href*='/jobs-internships/'], a[href*='/graduate-employers/'][href*='internship']"
    )

    out: list[JobNormalized] = []
    seen: set[str] = set()
    for a in anchors[:60]:
        job = _parse_anchor(a)
        if job is None or job.url in seen:
            continue
        seen.add(job.url)
        out.append(job)

    enrich_jobs_location_from_detail_pages(out, source_label="prosple")
    logger.info("Prosple: %s unique job links", len(out))
    return out


def fetch_with_browser(browser: Browser) -> list[JobNormalized]:
    """Scrape Prosple using an already-launched shared browser (no new process)."""
    try:
        with browser_page(browser) as page:
            return _scrape_with_page(page)
    except Exception:
        logger.exception("Prosple scrape failed (shared browser)")
        return []


def _fetch_sync() -> list[JobNormalized]:
    """Standalone scrape — launches its own browser (used outside pipeline)."""
    try:
        with playwright_session() as browser:
            return fetch_with_browser(browser)
    except Exception:
        logger.exception("Prosple scrape failed (standalone)")
        return []


async def fetch_jobs() -> list[JobNormalized]:
    return await asyncio.to_thread(_fetch_sync)


class ProspleScraper:
    source = "prosple"

    async def fetch_jobs(self) -> list[JobNormalized]:
        return await fetch_jobs()

    def fetch_jobs_with_browser(self, browser: Browser) -> list[JobNormalized]:
        """Used by pipeline to share one Chromium instance across scrapers."""
        return fetch_with_browser(browser)
