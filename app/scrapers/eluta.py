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


def _scrape_eluta_with_page(page) -> list[JobNormalized]:
    settings = get_settings()
    if not settings.eluta_enabled or settings.eluta_max_jobs <= 0:
        return []

    cap = settings.eluta_max_jobs
    max_pages = settings.eluta_max_pages
    base_list = str(settings.eluta_list_url).strip()
    if not base_list:
        return []

    collected: list[JobNormalized] = []
    seen_urls: set[str] = set()
    posted_default = datetime.now(timezone.utc).strftime("%Y-%m-%d")

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

        rows = parse_organic_jobs(html)
        if not rows:
            logger.info("Eluta: no organic jobs on page %s, stopping.", pnum)
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

    logger.info("Eluta: collected %s jobs (cap=%s)", len(collected), cap)
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
