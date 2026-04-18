"""Job listing and manual scan trigger."""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, desc, or_
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.database import get_db
from app.models.applied_url import AppliedUrl
from app.models.job import Job
from app.models.job_analysis import JobAnalysis
from app.services.pipeline import get_pipeline_state, run_full_pipeline
from app.utils.role_keywords import merged_focus_and_llm_tags
from app.utils.url_norm import normalize_application_url

router = APIRouter()


def _intern_role_boost() -> ColumnElement[int]:
    """1 when the job title looks like an intern / co-op / placement role (else 0).

    Used in ORDER BY DESC so internship-style postings sort above full-time roles
    within the same priority tier.
    """
    t = Job.title
    looks_intern = or_(
        t.ilike("%internship%"),   # covers internship / internships / internship→*
        t.ilike("% intern%"),      # covers ' intern', ' intern ', '/ intern', '(intern'
        t.ilike("intern %"),       # starts with 'intern '
        t.ilike("%co-op%"),        # covers ' co-op', 'co-op'
        t.ilike("%coop%"),
        t.ilike("% co op %"),
        t.ilike("%student placement%"),
        t.ilike("%summer student%"),
    )
    return case((looks_intern, 1), else_=0)


class AppliedPatch(BaseModel):
    """Mark whether the user has submitted an application for this posting."""

    applied: bool = Field(
        default=True,
        description="True sets applied_at to now; False clears it.",
    )


@router.get("")
def list_jobs(
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "default",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return recent jobs (paginated).

    sort_by=default        — priority → intern boost → match_score → created_at
    sort_by=priority_apply — Analyze APPLY first, then score desc; unanalyzed last
    """
    prio = case(
        (Job.priority == "HIGH", 1),
        (Job.priority == "MEDIUM", 2),
        (Job.priority == "LOW", 3),
        else_=5,
    )
    q = (
        db.query(Job)
        .order_by(
            prio,
            desc(_intern_role_boost()),
            desc(Job.match_score).nulls_last(),
            Job.created_at.desc(),
        )
    )
    total = q.count()
    rows = q.offset(skip).limit(limit).all()

    # Batch-fetch analyze results for this page.
    analyze_lookup = _analyze_lookup_map(db, rows)

    if sort_by == "priority_apply":
        _DECISION_ORDER = {"APPLY": 0, "STRETCH": 1, "SKIP": 3}
        rows = sorted(rows, key=lambda j: (
            _DECISION_ORDER.get((analyze_lookup.get(j.id) or {}).get("decision", ""), 2),
            -((analyze_lookup.get(j.id) or {}).get("score") or 0),
        ))

    applied_lookup = _applied_lookup_map(db, rows)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [_job_to_dict(j, applied_lookup=applied_lookup, analyze_data=analyze_lookup.get(j.id)) for j in rows],
    }


@router.get("/high-priority")
def list_high_priority(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Jobs with HIGH priority or match_score > 0.75, paginated."""
    prio = case(
        (Job.priority == "HIGH", 1),
        (Job.priority == "MEDIUM", 2),
        (Job.priority == "LOW", 3),
        else_=5,
    )
    q = (
        db.query(Job)
        .filter(
            or_(
                Job.priority == "HIGH",
                Job.match_score > 0.75,
            )
        )
        .order_by(
            prio,
            desc(_intern_role_boost()),
            desc(Job.match_score).nulls_last(),
            Job.created_at.desc(),
        )
    )
    total = q.count()
    rows = q.offset(skip).limit(limit).all()
    analyze_lookup = _analyze_lookup_map(db, rows)
    applied_lookup = _applied_lookup_map(db, rows)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [_job_to_dict(j, applied_lookup=applied_lookup, analyze_data=analyze_lookup.get(j.id)) for j in rows],
    }


@router.post("/run-scan")
def trigger_scan(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Start scrape → dedupe → score → notify in background; returns immediately.

    Returns 409-style payload if a scan is already running (no duplicate runs).
    Poll GET /jobs/scan-status for completion and results.
    """
    state = get_pipeline_state()
    if state["status"] == "running":
        return {
            "status": "already_running",
            "message": "A scan is already in progress. Poll /jobs/scan-status for updates.",
            "last_run_at": state["last_run_at"],
        }
    background_tasks.add_task(run_full_pipeline)
    return {
        "status": "queued",
        "message": "Scan started in background. Poll /jobs/scan-status for results.",
    }


@router.get("/scan-status")
def scan_status() -> dict[str, Any]:
    """Return current pipeline status and last run result."""
    return get_pipeline_state()


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return a single job with full (untruncated) description."""
    row = db.query(Job).filter(Job.id == job_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    applied_lookup = _applied_lookup_map(db, [row])
    analyze_lookup = _analyze_lookup_map(db, [row])
    data = _job_to_dict(row, applied_lookup=applied_lookup, analyze_data=analyze_lookup.get(row.id))
    # Override the truncated description with full text for the analysis SPA.
    data["description"] = row.description or ""
    data["description_truncated"] = False
    return data


@router.patch("/{job_id}/applied")
def patch_applied(
    job_id: int,
    body: AppliedPatch,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Set or clear application-submitted time for a job."""
    row = db.query(Job).filter(Job.id == job_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    nurl = normalize_application_url(row.url)
    if body.applied:
        ts = datetime.now(timezone.utc)
        row.applied_at = ts
        existing = db.query(AppliedUrl).filter(AppliedUrl.url_norm == nurl).one_or_none()
        if existing:
            existing.applied_at = ts
            db.add(existing)
        else:
            db.add(AppliedUrl(url_norm=nurl, applied_at=ts))
    else:
        row.applied_at = None
        db.query(AppliedUrl).filter(AppliedUrl.url_norm == nurl).delete(
            synchronize_session=False
        )

    db.add(row)
    db.commit()
    db.refresh(row)
    applied_lookup = _applied_lookup_map(db, [row])
    return _job_to_dict(row, applied_lookup=applied_lookup)


def _analyze_lookup_map(db: Session, jobs: list[Job]) -> dict[int, dict]:
    """Map job_id → {score, decision, confidence} from cached analyses."""
    ids = [j.id for j in jobs if j.id]
    if not ids:
        return {}
    result = {}
    for ja in db.query(JobAnalysis).filter(JobAnalysis.job_id.in_(ids)).all():
        try:
            d = json.loads(ja.result_json)
            result[ja.job_id] = {
                "score": d.get("score"),
                "decision": d.get("decision"),
                "confidence": d.get("confidence"),
            }
        except Exception:
            pass
    return result


def _applied_lookup_map(db: Session, jobs: list[Job]) -> dict[str, datetime]:
    """Map normalized URL → applied_at from persistent store."""
    norms = {normalize_application_url(j.url) for j in jobs if j.url}
    norms.discard("")
    if not norms:
        return {}
    rows = db.query(AppliedUrl).filter(AppliedUrl.url_norm.in_(norms)).all()
    return {r.url_norm: r.applied_at for r in rows}


def _job_to_dict(
    j: Job,
    *,
    applied_lookup: dict[str, datetime] | None = None,
    analyze_data: dict | None = None,
) -> dict[str, Any]:
    n = normalize_application_url(j.url)
    applied_at = j.applied_at
    if applied_lookup is not None and n:
        persisted = applied_lookup.get(n)
        if persisted is not None:
            applied_at = persisted

    return {
        "id": j.id,
        "title": j.title,
        "company": j.company,
        "location": j.location,
        "url": j.url,
        # Truncated to 4000 chars for API payload size; full text stored in DB.
        "description": (j.description or "")[:4000],
        "description_truncated": len(j.description or "") > 4000,
        "posted_at": j.posted_at,
        "source": j.source,
        "content_hash": j.content_hash,
        "is_updated": j.is_updated,
        "match_score": j.match_score,
        "priority": j.priority,
        "reason": j.reason,
        "notified_at": j.notified_at.isoformat() if j.notified_at else None,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "tags": merged_focus_and_llm_tags(
            list(j.tags) if j.tags else None,
            j.title,
            j.company,
            j.description or "",
        ),
        "applied_at": applied_at.isoformat() if applied_at else None,
        # Analyze fields — null when job has not been analyzed yet.
        "analyze_score": (analyze_data or {}).get("score"),
        "analyze_decision": (analyze_data or {}).get("decision"),
        "analyze_confidence": (analyze_data or {}).get("confidence"),
    }
