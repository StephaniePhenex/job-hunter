"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets must come from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite:///./data/intern_intel.db",
        description="SQLAlchemy database URL",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Job scoring: Gemini preferred when GEMINI_API_KEY is set; else OpenAI if OPENAI_API_KEY is set.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    github_internships_readme_url: str = Field(
        default=(
            "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"
        ),
    )
    # README can contain thousands of rows; cap per run to control LLM cost/latency.
    github_internships_max_rows: int = 200
    prosple_search_url: str = Field(
        default="https://ca.prosple.com/search-jobs?keywords=software+developer&order_by=relevance",
    )
    talentegg_internships_url: str = Field(
        default="https://talentegg.ca/latest-jobs",
        description="Listing page (avoid /internships/ which often returns HTTP 500).",
    )

    # Eluta (Canada): HTML list pages, e.g. Software-Engineer-jobs slug or search URL.
    eluta_enabled: bool = True
    eluta_list_url: str = Field(
        default="https://www.eluta.ca/Software-Engineer-jobs",
        description="First page of job search/list; pagination uses ?pg=N.",
    )
    eluta_max_jobs: int = Field(default=60, ge=0, description="Max rows collected per scan.")
    eluta_max_pages: int = Field(default=8, ge=1, description="Safety cap on list pages to fetch.")

    # After list scrape, GET job detail HTML and parse city/region (JSON-LD JobPosting).
    # Enabled by default: Prosple/TalentEgg only give country-level location ("Canada");
    # this upgrades them to city/region for accurate filtering and LLM scoring.
    job_location_detail_fetch_enabled: bool = True
    job_location_detail_max_per_source: int = 80
    job_location_detail_delay_sec: float = 0.2

    playwright_timeout_ms: int = 30_000
    playwright_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    scan_interval_hours: int = 6


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
