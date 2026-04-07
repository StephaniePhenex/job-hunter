"""APScheduler: periodic full pipeline runs."""

import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    """Start background jobs (idempotent)."""
    global _scheduler
    if _scheduler is not None:
        return

    settings = get_settings()
    interval = max(1, settings.scan_interval_hours)

    _scheduler = BackgroundScheduler(timezone="UTC")

    def run_job() -> None:
        from app.services.pipeline import run_full_pipeline

        try:
            run_full_pipeline()
        except Exception:
            logger.exception("Scheduled pipeline run failed")

    _scheduler.add_job(
        run_job,
        "interval",
        hours=interval,
        id="full_pipeline",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started: full pipeline every %s hour(s)", interval)


def shutdown_scheduler() -> None:
    """Stop scheduler on app shutdown."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def get_scheduler() -> BackgroundScheduler | None:
    """Expose scheduler for tests (optional)."""
    return _scheduler
