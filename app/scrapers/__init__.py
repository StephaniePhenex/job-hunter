"""Data source scrapers."""

from app.core.config import get_settings
from app.scrapers.eluta import ElutaScraper
from app.scrapers.github_internships import GitHubInternshipsScraper
from app.scrapers.prosple import ProspleScraper
from app.scrapers.talentegg import TalentEggScraper

_settings = get_settings()

# HTTP scrapers (httpx/async) — run concurrently in the event loop
HTTP_SCRAPERS = [
    GitHubInternshipsScraper(),
]

# Playwright scrapers — share ONE browser in the pipeline (see pipeline._collect_normalized)
PLAYWRIGHT_SCRAPERS = [
    ProspleScraper(),
    TalentEggScraper(),
]
# Eluta: TLS/anti-bot is unreliable with raw httpx; use Chromium like Prosple/TalentEgg.
if _settings.eluta_enabled:
    PLAYWRIGHT_SCRAPERS.append(ElutaScraper())

ALL_SCRAPERS = HTTP_SCRAPERS + PLAYWRIGHT_SCRAPERS

__all__ = [
    "ALL_SCRAPERS",
    "HTTP_SCRAPERS",
    "PLAYWRIGHT_SCRAPERS",
    "GitHubInternshipsScraper",
    "ElutaScraper",
    "ProspleScraper",
    "TalentEggScraper",
]
