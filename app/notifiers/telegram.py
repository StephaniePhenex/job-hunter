"""Telegram Bot API notifications."""

import logging
import time
from datetime import datetime, timezone
from html import escape

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job import Job

logger = logging.getLogger(__name__)


def should_notify(job: Job) -> bool:
    """Notify if HIGH priority or match_score > 0.75."""
    if job.notified_at is not None:
        return False
    if job.priority == "HIGH":
        return True
    if job.match_score is not None and job.match_score > 0.75:
        return True
    return False


def send_job_alert(db: Session, job: Job) -> bool:
    """Send Telegram message for one job; set notified_at on success."""
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.debug("Telegram not configured; skip notify for job %s", job.id)
        return False

    score = job.match_score if job.match_score is not None else 0.0
    reason = job.reason or ""
    text = (
        f"<b>{escape(job.title)}</b>\n"
        f"{escape(job.company)}\n"
        f"Score: {score:.2f}\n"
        f"Priority: {escape(job.priority or '')}\n\n"
        f"{escape(reason)}\n\n"
        f'<a href="{escape(job.url, quote=True)}">Apply / details</a>'
    )

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    for attempt in range(2):
        try:
            r = httpx.post(url, json=payload, timeout=30.0)
            r.raise_for_status()
            job.notified_at = datetime.now(timezone.utc)
            db.add(job)
            db.commit()
            logger.info("Telegram notification sent for job id=%s", job.id)
            return True
        except Exception:
            if attempt == 0:
                logger.warning(
                    "Telegram send failed for job id=%s; retrying in 3s", job.id
                )
                time.sleep(3)
            else:
                logger.exception(
                    "Telegram send failed for job id=%s after 2 attempts", job.id
                )
    return False


def notify_eligible_jobs(db: Session, jobs: list[Job]) -> int:
    """Send alerts for jobs that pass should_notify; return count sent."""
    sent = 0
    for job in jobs:
        if should_notify(job):
            if send_job_alert(db, job):
                sent += 1
    return sent
