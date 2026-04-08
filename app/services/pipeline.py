"""End-to-end: scrape → dedupe → score → notify."""

import asyncio
import logging
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.llm_client import score_job
from app.agents.profile import DEFAULT_USER_PROFILE
from app.core.database import SessionLocal
from app.models.job import Job
from app.notifiers.telegram import notify_eligible_jobs
from app.scrapers import HTTP_SCRAPERS, PLAYWRIGHT_SCRAPERS
from app.services.dedupe import compute_content_hash, compute_description_hash
from app.utils.role_keywords import (
    merge_llm_score_with_keyword_priority,
    merged_focus_and_llm_tags,
    passes_focus_role_keywords,
)
from app.utils.schemas import JobNormalized

logger = logging.getLogger(__name__)

# --- Concurrency guard: prevents scheduler + manual trigger from running simultaneously ---
_pipeline_lock = threading.Lock()
_pipeline_state: dict[str, Any] = {
    "status": "idle",          # "idle" | "running"
    "last_run_at": None,       # ISO-8601 UTC string
    "last_result": None,       # last run's return dict
}


def get_pipeline_state() -> dict[str, Any]:
    """Return a snapshot of current pipeline state (safe to expose via API)."""
    return dict(_pipeline_state)


async def _collect_normalized() -> list[JobNormalized]:
    """Collect jobs from all sources.

    HTTP scrapers (GitHub/httpx) run concurrently in the event loop.
    Playwright scrapers share ONE Chromium browser in a single background thread
    to avoid spawning multiple heavyweight browser processes simultaneously.
    """
    results: list[JobNormalized] = []

    # --- HTTP scrapers: concurrent async ---
    async def run_http(scraper: Any) -> None:
        try:
            jobs = await scraper.fetch_jobs()
            results.extend(jobs)
        except Exception:
            logger.exception("HTTP scraper failed: %s", getattr(scraper, "source", scraper))

    await asyncio.gather(*[run_http(s) for s in HTTP_SCRAPERS])

    # --- Playwright scrapers: one browser, sequential pages, one thread ---
    def run_playwright_scrapers() -> list[JobNormalized]:
        from app.utils.playwright import playwright_session

        items: list[JobNormalized] = []
        try:
            with playwright_session() as browser:
                for scraper in PLAYWRIGHT_SCRAPERS:
                    try:
                        jobs = scraper.fetch_jobs_with_browser(browser)
                        items.extend(jobs)
                        logger.info(
                            "Playwright scraper %s returned %s jobs",
                            scraper.source,
                            len(jobs),
                        )
                    except Exception:
                        logger.exception(
                            "Playwright scraper failed: %s", scraper.source
                        )
        except Exception:
            logger.exception("Playwright session failed; skipping browser scrapers")
        return items

    playwright_results = await asyncio.to_thread(run_playwright_scrapers)
    results.extend(playwright_results)

    return results


_SCORE_WORKERS = 5  # max concurrent OpenAI calls


def _score_many(items: list[JobNormalized]) -> list[Any]:
    """Score a batch of jobs concurrently (bounded ThreadPoolExecutor).

    Returns results in the same order as the input list.
    Falls back to LOW score on individual failures (score_job handles this internally).
    """
    if not items:
        return []

    def _one(item: JobNormalized) -> Any:
        return score_job(
            description=item.description,
            title=item.title,
            company=item.company,
            profile=DEFAULT_USER_PROFILE,
        )

    with ThreadPoolExecutor(max_workers=_SCORE_WORKERS) as pool:
        futures = [pool.submit(_one, item) for item in items]
        return [f.result() for f in futures]  # preserves submission order


def upsert_and_score_batch(db: Session, items: list[JobNormalized]) -> dict[str, int]:
    """Replace the entire job inventory for this run, then score and notify.

    Historical rows are **not** merged with previous scans: every successful pipeline run
    clears ``jobs`` first so the dashboard reflects only the latest scrape (plus filters).

    Three-pass approach:
      0. Delete all existing rows (full replace).
      1. Classify each scraped item as new / updated / unchanged (always new vs empty DB).
      2. Score all new + updated concurrently via ThreadPoolExecutor.
      3. Write all inserts + updates in one commit.
    """
    stats: dict[str, int] = {
        "new": 0,
        "updated": 0,
        "unchanged": 0,
        "scored": 0,
        "notified": 0,
        "cleared": 0,
    }

    # Snapshot notified_at by content_hash BEFORE clearing so previously-notified
    # jobs are not re-alerted after the table is wiped and re-populated.
    notified_snapshot: dict[str, Any] = {
        row.content_hash: row.notified_at
        for row in db.query(Job).filter(Job.notified_at.isnot(None)).all()
    }
    if notified_snapshot:
        logger.debug(
            "Pipeline: preserved notified_at for %s job(s)", len(notified_snapshot)
        )

    cleared = db.query(Job).delete(synchronize_session=False)
    db.flush()
    stats["cleared"] = cleared
    if cleared:
        logger.info("Pipeline: cleared %s previous job row(s) before this ingest", cleared)

    # --- Pass 1: classify ---
    to_insert: list[tuple[JobNormalized, str, str]] = []   # (item, content_hash, desc_hash)
    to_update: list[tuple[Job, JobNormalized, str]] = []   # (row, item, new_desc_hash)

    for item in items:
        ch = compute_content_hash(item)
        dh = compute_description_hash(item.description)
        row = db.query(Job).filter(Job.content_hash == ch).one_or_none()
        if row is None:
            to_insert.append((item, ch, dh))
        elif row.description_hash != dh:
            to_update.append((row, item, dh))
        else:
            stats["unchanged"] += 1

    # --- Pass 2: score new + updated concurrently ---
    insert_items = [item for item, _, _ in to_insert]
    update_items = [item for _, item, _ in to_update]
    all_scores = _score_many(insert_items + update_items)

    n_insert = len(to_insert)
    insert_scores = all_scores[:n_insert]
    update_scores = all_scores[n_insert:]

    logger.info(
        "Scoring complete: %s new, %s updated (workers=%s)",
        n_insert, len(to_update), _SCORE_WORKERS,
    )

    # --- Pass 3: write ---
    to_notify: list[Job] = []

    for (item, ch, dh), score in zip(to_insert, insert_scores):
        score = merge_llm_score_with_keyword_priority(
            score, item.title, item.company, item.description
        )
        tags = merged_focus_and_llm_tags(
            score.tags, item.title, item.company, item.description
        )
        job = Job(
            title=item.title,
            company=item.company,
            location=item.location,
            url=item.url,
            description=item.description,
            posted_at=item.posted_at,
            source=item.source,
            content_hash=ch,
            description_hash=dh,
            is_updated=False,
            match_score=score.match_score,
            priority=score.priority,
            reason=score.reason,
            tags=tags,
            # Restore previous notified_at so we don't re-alert on every scan
            notified_at=notified_snapshot.get(ch),
        )
        db.add(job)
        db.flush()
        to_notify.append(job)
        stats["new"] += 1
        stats["scored"] += 1

    for (row, item, dh), score in zip(to_update, update_scores):
        score = merge_llm_score_with_keyword_priority(
            score, item.title, item.company, item.description
        )
        row.description = item.description
        row.description_hash = dh
        row.title = item.title
        row.company = item.company
        row.location = item.location
        row.url = item.url
        row.posted_at = item.posted_at
        row.is_updated = True
        row.updated_at = datetime.now(timezone.utc)
        row.match_score = score.match_score
        row.priority = score.priority
        row.reason = score.reason
        row.tags = merged_focus_and_llm_tags(
            score.tags, item.title, item.company, item.description
        )
        # Reset so updated high-signal jobs can alert again
        row.notified_at = None
        db.add(row)
        to_notify.append(row)
        stats["updated"] += 1
        stats["scored"] += 1

    db.commit()

    sent = notify_eligible_jobs(db, to_notify)
    stats["notified"] = sent
    return stats


def run_full_pipeline() -> dict[str, Any]:
    """Sync entrypoint used by API and scheduler.

    Thread-safe: rejects concurrent runs via a non-blocking lock so that
    APScheduler background threads and manual /run-scan calls never overlap.
    """
    global _pipeline_state

    if not _pipeline_lock.acquire(blocking=False):
        logger.warning("Pipeline already running — concurrent call rejected")
        return {"ok": False, "reason": "already_running"}

    _pipeline_state = {
        "status": "running",
        "last_run_at": datetime.now(timezone.utc).isoformat(),
        "last_result": None,
    }

    try:
        items = asyncio.run(_collect_normalized())
        scraped_total = len(items)
        by_source_scraped: Counter[str] = Counter(j.source for j in items)

        items = [
            j
            for j in items
            if passes_focus_role_keywords(j.title, j.company, j.description)
        ]
        keyword_dropped = scraped_total - len(items)
        by_source_after_kw: Counter[str] = Counter(j.source for j in items)

        logger.info(
            "Focus role keyword filter: %s -> %s rows (dropped %s)",
            scraped_total,
            len(items),
            keyword_dropped,
        )
        logger.info("By source (scraped): %s", dict(by_source_scraped))
        logger.info("By source (after keyword gate): %s", dict(by_source_after_kw))
        db = SessionLocal()
        try:
            stats = upsert_and_score_batch(db, items)
            result: dict[str, Any] = {
                "ok": True,
                "scraped_total": scraped_total,
                "keyword_filtered_out": keyword_dropped,
                "collected": len(items),
                "by_source_scraped": dict(by_source_scraped),
                "by_source_after_keywords": dict(by_source_after_kw),
                **stats,
            }
        finally:
            db.close()

        _pipeline_state["last_result"] = result
        return result

    except Exception:
        logger.exception("Pipeline run raised an unexpected exception")
        result = {"ok": False, "reason": "exception; see logs"}
        _pipeline_state["last_result"] = result
        return result

    finally:
        _pipeline_state["status"] = "idle"
        _pipeline_lock.release()
