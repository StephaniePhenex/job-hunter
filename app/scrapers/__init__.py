"""Data source scrapers."""

from app.scrapers.github_internships import GitHubInternshipsScraper
from app.scrapers.prosple import ProspleScraper
from app.scrapers.talentegg import TalentEggScraper

# HTTP scrapers (httpx/async) — run concurrently in the event loop
HTTP_SCRAPERS = [
    GitHubInternshipsScraper(),
]

# Playwright scrapers — share ONE browser in the pipeline (see pipeline._collect_normalized)
PLAYWRIGHT_SCRAPERS = [
    ProspleScraper(),
    TalentEggScraper(),
]

ALL_SCRAPERS = HTTP_SCRAPERS + PLAYWRIGHT_SCRAPERS

__all__ = [
    "ALL_SCRAPERS",
    "HTTP_SCRAPERS",
    "PLAYWRIGHT_SCRAPERS",
    "GitHubInternshipsScraper",
    "ProspleScraper",
    "TalentEggScraper",
]
