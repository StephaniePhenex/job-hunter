"""TalentEgg — Playwright job listing pages.

Note: Paths like /internships/ and /jobs/ often return HTTP 500 on the server (2026).
The stable entry point we use is /latest-jobs (200) with links to /employer/.../jobs/....

Inbound policy (this source only, before global pipeline keyword filter):
- Cards with clearly US-only locations are dropped (Canada-focused product).
- Role keyword matching is applied globally in ``pipeline`` for all sources.
- Location is parsed to city + region when visible on the listing card.
"""

import asyncio
import logging
import re
from urllib.parse import urljoin

from playwright.sync_api import Browser

from app.core.config import get_settings
from app.utils.location_enrichment import enrich_jobs_location_from_detail_pages
from app.utils.playwright import browser_page, playwright_session
from app.utils.schemas import JobNormalized

logger = logging.getLogger(__name__)

_TALENTEGG_ORIGIN = "https://talentegg.ca"

# Fallback chain: try each URL in order until one returns job anchors.
# /latest-jobs is now flooded by Job Bank listings (filtered via _JOB_BANK_PATH).
# The keyword URL surfaces actual employer-posted tech jobs when available.
_FALLBACK_URLS = [
    "https://talentegg.ca/latest-jobs",
    "https://talentegg.ca/find-a-job/keyword/developer/",
    "https://talentegg.ca/find-a-job/keyword/software/",
]
_FALLBACK_LIST_URL = _FALLBACK_URLS[0]  # kept for backward-compat log messages

_JOB_DETAIL_PATH = re.compile(r"/employer/[^/]+/jobs/.+", re.IGNORECASE)

# Job Bank is the Government of Canada's generic job board, syndicated onto TalentEgg.
# It floods /latest-jobs with unrelated roles (construction, food service, etc.).
_JOB_BANK_PATH = re.compile(r"/employer/job-bank/", re.IGNORECASE)

_CA_PROVINCE = re.compile(
    r"(Ontario|Quebec|British Columbia|Alberta|Manitoba|Saskatchewan|Nova Scotia|"
    r"New Brunswick|Prince Edward Island|Newfoundland|Northwest Territories|Yukon|Nunavut|PEI)\b",
    re.IGNORECASE,
)

_US_STATE_END = re.compile(
    r",\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|MI|MN|"
    r"MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VA|VT|WA|WI|WV|WY|DC)\s*$",
    re.IGNORECASE,
)

_CA_CODES = {"ON", "BC", "AB", "QC", "MB", "SK", "NS", "NB", "PE", "NL", "YT", "NT", "NU"}


def _passes_canada_geo(location_line: str, card_text: str) -> bool:
    """Drop TalentEgg rows that are clearly US-only (this product is Canada-focused)."""
    blob = f"{location_line}\n{card_text}".lower()
    if _CA_PROVINCE.search(location_line) or _CA_PROVINCE.search(card_text):
        return True
    if re.search(
        r"\b(toronto|montreal|vancouver|calgary|ottawa|edmonton|winnipeg|waterloo|"
        r"mississauga|kitchener|hamilton|victoria|halifax|saskatoon|regina|gatineau|"
        r"laval|burnaby|surrey|kelowna|london\s*,\s*on)\b",
        blob,
    ):
        return True

    m = _US_STATE_END.search(location_line.strip())
    if m:
        code = m.group(1).upper()
        if code not in _CA_CODES:
            return False

    if re.search(
        r"\b(nyc|new york,\s*ny|manhattan|brooklyn|san francisco,\s*ca|los angeles,\s*ca|"
        r"chicago,\s*il|boston,\s*ma|seattle,\s*wa|austin,\s*tx)\b",
        blob,
    ):
        return False

    return True


def _strip_posted_ago(line: str) -> str:
    return re.split(r"\d+\s*(hour|hours|day|days|minute|min|week|weeks)s?\s*ago", line, flags=re.I)[0].strip()


def _parse_location_line(lines: list[str], title: str) -> str:
    """Pick 'City, Province' / 'City, ST' from card lines; drop posted-ago suffix."""
    for line in lines[1:]:
        s = _strip_posted_ago(line)
        if "," in s and len(s) > 4:
            return s[:512]
    return ""


def _location_from_card_blob(card_text: str, lines: list[str], title: str) -> str:
    """Listing card lines first; then regex over full card (DOM often merges lines oddly)."""
    loc = _parse_location_line(lines, title)
    if loc:
        return loc
    m = re.search(
        r"\b([A-Za-z][A-Za-z\s\-']{2,58},\s*(?:ON|BC|AB|QC|MB|SK|NS|NB|PE|NL|YT|NT|NU))\b",
        card_text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()[:512]
    return ""


def _card_inner_text(anchor) -> str:
    """Walk up DOM until we get a richer card (title + location + time)."""
    return anchor.evaluate(
        """(el) => {
      let n = el;
      for (let i = 0; i < 6 && n; i++) {
        const t = (n.innerText || '').trim();
        if (t.length > (el.innerText || '').length + 15) return t;
        n = n.parentElement;
      }
      return (el.parentElement && el.parentElement.innerText) || el.innerText || '';
    }"""
    )


def _parse_anchor(a) -> JobNormalized | None:
    href = (a.get_attribute("href") or "").strip()
    if not href or not href.startswith("http"):
        if href.startswith("/"):
            href = urljoin(_TALENTEGG_ORIGIN + "/", href.lstrip("/"))
        elif href.startswith("//"):
            href = "https:" + href
    if "talentegg.ca" not in href.lower():
        return None
    if not _JOB_DETAIL_PATH.search(href):
        return None
    # Skip Government of Canada Job Bank listings — they syndicate thousands of
    # unrelated roles (construction, food service, etc.) onto TalentEgg.
    if _JOB_BANK_PATH.search(href):
        return None

    card_text = _card_inner_text(a)
    lines = [ln.strip() for ln in card_text.splitlines() if ln.strip()]
    title = (a.inner_text() or "").strip().split("\n")[0][:512] if (a.inner_text() or "").strip() else ""
    if not title and lines:
        title = lines[0][:512]

    location_line = _location_from_card_blob(card_text, lines, title)
    if location_line and not _passes_canada_geo(location_line, card_text):
        logger.debug("TalentEgg skip (non-Canada location): %s | %s", title[:60], location_line[:80])
        return None

    # Card text no longer includes company name; extract from URL slug instead.
    # e.g. /employer/shopify-inc/jobs/... → "Shopify Inc"
    company = ""
    m = re.search(r"/employer/([^/]+)/jobs/", href)
    if m:
        company = m.group(1).replace("-", " ").title()[:512]

    loc_display = location_line or "Canada"

    return JobNormalized(
        title=title or "Job posting",
        company=company,
        location=loc_display,
        url=href.split("?", 1)[0],
        description=card_text[:2000],
        posted_at="",
        source="talentegg",
    )


def _query_job_anchors(page):
    selectors = (
        "a[href^='https://talentegg.ca/employer/'][href*='/jobs/']",
        "a[href^='http://talentegg.ca/employer/'][href*='/jobs/']",
        "a[href^='https://www.talentegg.ca/employer/'][href*='/jobs/']",
        "a[href^='/employer/'][href*='/jobs/']",
    )
    seen: set[str] = set()
    out = []
    for sel in selectors:
        for el in page.query_selector_all(sel):
            href = el.get_attribute("href") or ""
            if href in seen:
                continue
            seen.add(href)
            out.append(el)
    return out


def _scrape_with_page(page) -> list[JobNormalized]:
    settings = get_settings()
    primary = str(settings.talentegg_internships_url).strip()

    def load(url: str) -> None:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        for _ in range(8):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(600)

    load(primary)
    anchors = _query_job_anchors(page)

    # Walk the fallback chain until we get job links.
    if not anchors:
        for fallback in _FALLBACK_URLS:
            if fallback.rstrip("/") == primary.rstrip("/"):
                continue
            logger.warning("TalentEgg: 0 job links from %s; trying %s", primary, fallback)
            load(fallback)
            anchors = _query_job_anchors(page)
            if anchors:
                break

    out: list[JobNormalized] = []
    seen_urls: set[str] = set()
    for a in anchors[:400]:
        job = _parse_anchor(a)
        if job is None or job.url in seen_urls:
            continue
        seen_urls.add(job.url)
        out.append(job)

    enrich_jobs_location_from_detail_pages(out, source_label="talentegg")

    logger.info("TalentEgg: %s job rows (Canada geo filter only; role keywords in pipeline)", len(out))
    return out


def fetch_with_browser(browser: Browser) -> list[JobNormalized]:
    """Scrape TalentEgg using an already-launched shared browser (no new process)."""
    try:
        with browser_page(browser) as page:
            return _scrape_with_page(page)
    except Exception:
        logger.exception("TalentEgg scrape failed (shared browser)")
        return []


def _fetch_sync() -> list[JobNormalized]:
    """Standalone scrape — launches its own browser (used outside pipeline)."""
    try:
        with playwright_session() as browser:
            return fetch_with_browser(browser)
    except Exception:
        logger.exception("TalentEgg scrape failed (standalone)")
        return []


async def fetch_jobs() -> list[JobNormalized]:
    return await asyncio.to_thread(_fetch_sync)


class TalentEggScraper:
    source = "talentegg"

    async def fetch_jobs(self) -> list[JobNormalized]:
        return await fetch_jobs()

    def fetch_jobs_with_browser(self, browser: Browser) -> list[JobNormalized]:
        """Used by pipeline to share one Chromium instance across scrapers."""
        return fetch_with_browser(browser)
