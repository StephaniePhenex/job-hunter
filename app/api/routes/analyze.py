"""POST /api/analyze — deep job match analysis via LLM + Deterministic Guard.

Cache layer (Phase 2):
  - First call: run LLM, persist result in job_analyses table.
  - Subsequent calls: return cached result (unless force_refresh=true).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.analyze import AnalyzeResult, analyze_job_llm, apply_guard, _MOCK_RESULT
from app.agents.profile import load_user_profile, resumes_as_dicts
from app.core.config import get_settings
from app.core.database import get_db
from app.models.job import Job
from app.models.job_analysis import JobAnalysis

router = APIRouter()


class AnalyzeRequest(BaseModel):
    job_id: int
    force_refresh: bool = Field(default=False, description="Bypass cache and re-run analysis.")


@router.post("", response_model=None)
def analyze_job(body: AnalyzeRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Run deep match analysis for a single job posting.

    Data flow: cache hit → return; miss → LLM → Pydantic → Guard → cache → response.
    Set ANALYZE_USE_MOCK=false (env) to call a real LLM.
    """
    row = db.query(Job).filter(Job.id == body.job_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # ─── Cache check ─────────────────────────────────────────────────────────
    if not body.force_refresh:
        cached = db.query(JobAnalysis).filter(JobAnalysis.job_id == body.job_id).one_or_none()
        if cached:
            return json.loads(cached.result_json)

    # ─── Run analysis ─────────────────────────────────────────────────────────
    profile = load_user_profile()
    resumes = resumes_as_dicts(profile)
    valid_resume_ids = [r["id"] for r in resumes]

    settings = get_settings()

    if settings.analyze_use_mock:
        result = _MOCK_RESULT
    else:
        result = analyze_job_llm(
            title=row.title or "",
            company=row.company or "",
            description=(row.description or "")[:12000],
            profile=profile,
            resumes=resumes,
        )

    result = apply_guard(result, valid_resume_ids=valid_resume_ids)
    result_dict = result.model_dump()

    # ─── Persist to cache ─────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    cached_row = db.query(JobAnalysis).filter(JobAnalysis.job_id == body.job_id).one_or_none()
    if cached_row:
        cached_row.result_json = json.dumps(result_dict)
        cached_row.updated_at = now
    else:
        db.add(JobAnalysis(job_id=body.job_id, result_json=json.dumps(result_dict), created_at=now, updated_at=now))
    db.commit()

    return result_dict
