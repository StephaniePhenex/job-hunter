"""Eluta.ca — Playwright HTML scraper for organic job listings (Canada).

Plain httpx can fail TLS handshake with eluta.ca in some environments; Chromium matches
curl/browser behaviour.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import Browser

from app.core.config import get_settings
from app.utils.playwright import browser_page, playwright_session
from app.utils.schemas import JobNormalized

logger = logging.getLogger(__name__)

_BASE = "https://www.eluta.ca"


def _job_url_from_data_attr(data_url: str) -> str:
    du = (data_url or "").strip()
    if not du:
        return ""
    if du.startswith("http"):
        return du
    return urljoin(_BASE + "/", du.lstrip("/"))


def _list_url_with_page(base: str, page: int) -> str:
    base = base.strip()
    if page <= 1:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}pg={page}"


def parse_organic_jobs(html: str) -> list[dict[str, str]]:
    """Extract job fields from Eluta search HTML (unit tests use this with fixtures)."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, str]] = []
    for row in soup.select("div.organic-job"):
        data_url = (row.get("data-url") or "").strip()
        url = _job_url_from_data_attr(data_url)
        if not url:
            continue
        title_a = row.select_one("a.lk-job-title")
        title = ""
        if title_a:
            title = (title_a.get("title") or title_a.get_text(strip=True) or "").strip()
        emp_a = row.select_one("a.employer, a.lk-employer")
        company = (emp_a.get_text(strip=True) if emp_a else "") or ""
        loc_span = row.select_one("span.location span")
        location = (loc_span.get_text(strip=True) if loc_span else "") or ""
        desc_sp = row.select_one("span.description")
        description = ""
        if desc_sp:
            description = desc_sp.get_text(" ", strip=True)
        seen = row.select_one("a.lastseen")
        posted = ""
        if seen:
            posted = (seen.get_text(strip=True) or "")[:128]
        out.append(
            {
                "url": url,
                "title": title[:512],
                "company": company[:512],
                "location": location[:512],
                "description": description[:12000],
                "posted_at": posted,
            }
        )
    return out


def _scrape_one_url(
    page,
    base_list: str,
    max_pages: int,
    cap: int,
    seen_urls: set[str],
    posted_default: str,
    bot_blocked: list[bool],
) -> list[JobNormalized]:
    """Scrape one Eluta search URL across up to max_pages pages.

    Shares seen_urls for cross-URL deduplication.
    Sets bot_blocked[0]=True and stops early if a challenge page is detected.
    """
    collected: list[JobNormalized] = []
    for pnum in range(1, max_pages + 1):
        if len(collected) >= cap:
            break
        url = _list_url_with_page(base_list, pnum)
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            html = page.content()
        except Exception:
            logger.exception("Eluta page.goto failed: %s", url)
            break

        page_title = page.title().lower()
        if "user verification" in page_title or "are you a human" in html.lower():
            logger.warning(
                "Eluta: bot-detection triggered on %s — stopping all URLs for this run", url
            )
            bot_blocked[0] = True
            break

        rows = parse_organic_jobs(html)
        if not rows:
            logger.info("Eluta: no organic jobs on page %s of %s, stopping.", pnum, base_list)
            break

        for row in rows:
            if len(collected) >= cap:
                break
            u = row["url"]
            if u in seen_urls:
                continue
            seen_urls.add(u)
            collected.append(
                JobNormalized(
                    title=row["title"] or "Job posting",
                    company=row["company"] or "",
                    location=row["location"],
                    url=u,
                    description=row["description"],
                    posted_at=row["posted_at"] or posted_default,
                    source="eluta",
                )
            )

        page.wait_for_timeout(random.randint(300, 900))

    return collected


def _scrape_eluta_with_page(page) -> list[JobNormalized]:
    settings = get_settings()
    if not settings.eluta_enabled or settings.eluta_max_jobs <= 0:
        return []

    cap = settings.eluta_max_jobs
    max_pages = settings.eluta_max_pages
    primary_url = str(settings.eluta_list_url).strip()
    if not primary_url:
        return []

    # Build full list of URLs: primary + any extras from config
    all_urls = [primary_url]
    extra_raw = str(settings.eluta_extra_urls).strip()
    if extra_raw:
        for u in extra_raw.split(","):
            u = u.strip()
            if u and u != primary_url:
                all_urls.append(u)

    collected: list[JobNormalized] = []
    seen_urls: set[str] = set()
    posted_default = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bot_blocked = [False]

    # Warm-up: visit homepage first to establish session/cookies.
    try:
        page.goto("https://www.eluta.ca/", wait_until="domcontentloaded")
        page.wait_for_timeout(random.randint(2500, 4000))
    except Exception:
        logger.debug("Eluta: homepage warm-up failed; proceeding anyway")

    for i, base_list in enumerate(all_urls):
        if len(collected) >= cap or bot_blocked[0]:
            break
        remaining_cap = cap - len(collected)
        logger.info("Eluta: scraping URL %d/%d: %s", i + 1, len(all_urls), base_list)
        batch = _scrape_one_url(
            page, base_list, max_pages, remaining_cap, seen_urls, posted_default, bot_blocked
        )
        collected.extend(batch)
        logger.info("Eluta: +%d jobs from URL %d (total so far: %d)", len(batch), i + 1, len(collected))
        if i < len(all_urls) - 1 and not bot_blocked[0]:
            page.wait_for_timeout(random.randint(1000, 2000))

    logger.info("Eluta: collected %d unique jobs across %d URL(s) (cap=%d)", len(collected), len(all_urls), cap)
    return collected


def fetch_with_browser(browser: Browser) -> list[JobNormalized]:
    """Scrape Eluta using the shared pipeline browser."""
    try:
        with browser_page(browser) as page:
            return _scrape_eluta_with_page(page)
    except Exception:
        logger.exception("Eluta scrape failed (shared browser)")
        return []


def _fetch_sync_standalone() -> list[JobNormalized]:
    try:
        with playwright_session() as browser:
            return fetch_with_browser(browser)
    except Exception:
        logger.exception("Eluta scrape failed (standalone)")
        return []


async def fetch_jobs() -> list[JobNormalized]:
    return await asyncio.to_thread(_fetch_sync_standalone)


class ElutaScraper:
    """Wrapper: pipeline uses ``fetch_jobs_with_browser``; async ``fetch_jobs`` for scripts."""

    source = "eluta"

    async def fetch_jobs(self) -> list[JobNormalized]:
        return await fetch_jobs()

    def fetch_jobs_with_browser(self, browser: Browser) -> list[JobNormalized]:
        return fetch_with_browser(browser)
