"""Persisted job posting with dedupe hashes and AI scores."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Job(Base):
    """Normalized internship row; unique on content_hash (title + company + url)."""

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_content_hash", "content_hash", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(512), nullable=False)
    location: Mapped[str] = mapped_column(String(512), default="")
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[str] = mapped_column(String(128), default="")
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description_hash: Mapped[str] = mapped_column(String(64), default="")

    is_updated: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Day 7: LLM/rule-derived labels (e.g. web3, backend, media)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # User marks application submitted
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
