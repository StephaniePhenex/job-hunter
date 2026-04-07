"""Scraper protocol."""

from typing import Protocol

from app.utils.schemas import JobNormalized


class JobScraper(Protocol):
    """Each data source implements async fetch_jobs."""

    source: str

    async def fetch_jobs(self) -> list[JobNormalized]: ...
