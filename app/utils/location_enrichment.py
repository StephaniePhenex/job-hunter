"""Replace coarse scraper locations (e.g. ``Canada``) with city/region from the job detail HTML."""

from __future__ import annotations

import logging
import time

import httpx
from httpx import HTTPStatusError

from app.core.config import get_settings
from app.utils.job_location_html import extract_location_from_job_html
from app.utils.schemas import JobNormalized

logger = logging.getLogger(__name__)


def location_needs_detail_enrichment(location: str) -> bool:
    """True when listing only gave country-level or empty location."""
    s = (location or "").strip().lower()
    return (not s) or (s == "canada")


def enrich_jobs_location_from_detail_pages(
    jobs: list[JobNormalized],
    *,
    source_label: str = "scraper",
) -> None:
    """Best-effort GET each job URL and parse JobPosting JSON-LD (or fallbacks)."""
    settings = get_settings()
    if not settings.job_location_detail_fetch_enabled:
        return

    max_n = max(0, settings.job_location_detail_max_per_source)
    delay = max(0.0, settings.job_location_detail_delay_sec)
    if max_n == 0:
        return

    headers = {
        "User-Agent": settings.playwright_user_agent,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    n = 0
    capped_logged = False

    with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
        for j in jobs:
            if n >= max_n:
                if not capped_logged:
                    logger.info(
                        "%s: location detail fetch cap reached (%s)",
                        source_label,
                        max_n,
                    )
                    capped_logged = True
                break
            if not location_needs_detail_enrichment(j.location):
                continue
            for attempt in range(3):
                try:
                    r = client.get(j.url)
                    r.raise_for_status()
                    loc = extract_location_from_job_html(r.text)
                    if loc and len(loc.strip()) > 2:
                        j.location = loc.strip()[:512]
                        n += 1
                    break
                except HTTPStatusError as exc:
                    if exc.response.status_code == 429 and attempt < 2:
                        backoff = 5 * (2 ** attempt)  # 5s, 10s
                        logger.warning(
                            "%s: rate-limited (429) on %s; backing off %ss (attempt %s/3)",
                            source_label,
                            (j.url or "")[:80],
                            backoff,
                            attempt + 1,
                        )
                        time.sleep(backoff)
                    else:
                        logger.debug(
                            "%s: location enrich HTTP %s for %s",
                            source_label,
                            exc.response.status_code,
                            (j.url or "")[:96],
                        )
                        break
                except Exception:
                    logger.debug(
                        "%s: location enrich failed for %s",
                        source_label,
                        (j.url or "")[:96],
                    )
                    break
            if delay:
                time.sleep(delay)

    if n:
        logger.info("%s: enriched location from detail pages for %s jobs", source_label, n)
