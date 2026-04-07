"""Normalized job schema (API and scrapers)."""

from pydantic import BaseModel, Field


class JobNormalized(BaseModel):
    """Canonical shape returned by all scrapers."""

    title: str = Field(default="", max_length=512)
    company: str = Field(default="", max_length=512)
    location: str = Field(default="", max_length=512)
    url: str = Field(default="", max_length=2048)
    description: str = ""
    posted_at: str = Field(default="", max_length=128)
    source: str = Field(..., max_length=64)
