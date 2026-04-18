"""POST /api/optimize        — sync Writer → Critic (D16)
POST /api/optimize/stream   — SSE streaming Writer → Critic (D17)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.optimize import OptimizeResult, optimize_resume, optimize_resume_stream
from app.agents.profile import load_user_profile
from app.core.database import get_db
from app.models.job import Job

router = APIRouter()


class OptimizeRequest(BaseModel):
    job_id: int
    resume_id: str = ""   # empty → use first resume in profile


def _resolve(body: OptimizeRequest, db: Session) -> tuple[Job, Any]:
    """Return (job_row, resume_entry) or raise 404."""
    row = db.query(Job).filter(Job.id == body.job_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = load_user_profile()
    if not profile.resumes:
        raise HTTPException(status_code=422, detail="No resumes configured in user_profile.yaml")

    if body.resume_id:
        entry = next((r for r in profile.resumes if r.id == body.resume_id), None)
        if entry is None:
            raise HTTPException(status_code=422, detail=f"Resume '{body.resume_id}' not found")
    else:
        entry = profile.resumes[0]

    return row, entry, profile


@router.post("", response_model=None)
def optimize_sync(body: OptimizeRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Synchronous optimize: blocks until Writer + Critic complete."""
    row, entry, profile = _resolve(body, db)
    result: OptimizeResult = optimize_resume(
        title=row.title or "",
        company=row.company or "",
        job_description=(row.description or "")[:8000],
        resume_entry=entry,
        profile=profile,
    )
    return result.model_dump()


@router.post("/stream")
def optimize_stream(body: OptimizeRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """SSE streaming optimize.

    Client consumes lines of the form:
        data: {"type": "token"|"status"|"done"|"error", ...}
    """
    row, entry, profile = _resolve(body, db)

    def generator():
        yield from optimize_resume_stream(
            title=row.title or "",
            company=row.company or "",
            job_description=(row.description or "")[:8000],
            resume_entry=entry,
            profile=profile,
        )

    return StreamingResponse(generator(), media_type="text/event-stream")
