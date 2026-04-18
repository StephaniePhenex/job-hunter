"""D1 + D2: AnalyzeResult schema validation, Guard rules, and /api/analyze endpoint."""

import pytest
from pydantic import ValidationError

from app.agents.analyze import (
    AnalyzeDimensions,
    AnalyzeResult,
    AnalyzeStrategy,
    apply_guard,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_result(**kwargs) -> AnalyzeResult:
    defaults = dict(
        score=72,
        dimensions=AnalyzeDimensions(hard_skills=75, experience=65, synergy=80),
        decision="APPLY",
        confidence="MEDIUM",
        strengths=["S1", "S2"],
        gaps=["G1"],
        recommended_resume_id="",
        strategy=AnalyzeStrategy(
            focus="fullstack",
            key_message="Key message here.",
            risk="Some risk.",
        ),
    )
    defaults.update(kwargs)
    return AnalyzeResult(**defaults)


# ─── Schema validation ────────────────────────────────────────────────────────

def test_valid_result_round_trips():
    r = _make_result()
    assert r.score == 72
    assert r.decision == "APPLY"
    assert r.guard_adjusted is False


def test_score_bounds():
    with pytest.raises(ValidationError):
        _make_result(score=101)
    with pytest.raises(ValidationError):
        _make_result(score=-1)


def test_decision_enum():
    with pytest.raises(ValidationError):
        _make_result(decision="MAYBE")  # type: ignore[arg-type]


def test_confidence_enum():
    with pytest.raises(ValidationError):
        _make_result(confidence="CERTAIN")  # type: ignore[arg-type]


def test_strengths_capped_at_3():
    r = _make_result(strengths=["S1", "S2", "S3", "S4", "S5"])
    assert len(r.strengths) == 3


def test_gaps_capped_at_2():
    r = _make_result(gaps=["G1", "G2", "G3"])
    assert len(r.gaps) == 2


def test_dimensions_bounds():
    with pytest.raises(ValidationError):
        AnalyzeDimensions(hard_skills=101, experience=50, synergy=50)


# ─── Deterministic Guard ─────────────────────────────────────────────────────

def test_guard_score_cap_when_gaps_gte2_and_score_gt85():
    r = _make_result(score=90, gaps=["G1", "G2"])
    out = apply_guard(r, valid_resume_ids=[])
    assert out.score == 80
    assert out.guard_adjusted is True
    assert any("capped" in n for n in out.guard_notes)


def test_guard_no_cap_when_single_gap():
    r = _make_result(score=90, gaps=["G1"])
    out = apply_guard(r, valid_resume_ids=[])
    assert out.score == 90
    assert out.guard_adjusted is False


def test_guard_apply_to_stretch_when_score_lt65():
    r = _make_result(score=60, decision="APPLY")
    out = apply_guard(r, valid_resume_ids=[])
    assert out.decision == "STRETCH"
    assert out.guard_adjusted is True


def test_guard_stretch_to_skip_when_score_lt40():
    r = _make_result(score=35, decision="STRETCH")
    out = apply_guard(r, valid_resume_ids=[])
    assert out.decision == "SKIP"
    assert out.guard_adjusted is True


def test_guard_apply_to_skip_when_score_lt40():
    """APPLY < 40 should cascade: first → STRETCH, then → SKIP (same pass)."""
    r = _make_result(score=35, decision="APPLY")
    out = apply_guard(r, valid_resume_ids=[])
    assert out.decision == "SKIP"


def test_guard_resume_id_fallback():
    r = _make_result(recommended_resume_id="bad-id")
    out = apply_guard(r, valid_resume_ids=["resume-a", "resume-b"])
    assert out.recommended_resume_id == "resume-a"
    assert out.guard_adjusted is True


def test_guard_valid_resume_id_unchanged():
    r = _make_result(recommended_resume_id="resume-a")
    out = apply_guard(r, valid_resume_ids=["resume-a", "resume-b"])
    assert out.recommended_resume_id == "resume-a"
    assert out.guard_adjusted is False


def test_guard_no_change_returns_same_object_fields():
    r = _make_result(score=72, decision="APPLY", gaps=["G1"])
    out = apply_guard(r, valid_resume_ids=[])
    assert out.guard_adjusted is False
    assert out.guard_notes == []


# ─── /api/analyze endpoint (mock mode) ───────────────────────────────────────

def test_analyze_endpoint_mock(client):
    """POST /api/analyze with a seeded job returns mock AnalyzeResult shape."""
    from app.core.database import SessionLocal
    from app.models.job import Job

    # Seed one job.
    db = SessionLocal()
    job = Job(title="Software Engineer", company="Acme", url="https://example.com", source="test", content_hash="hash-acme-1")
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    resp = client.post("/api/analyze", json={"job_id": job_id})
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert data["decision"] in ("APPLY", "SKIP", "STRETCH")
    assert data["confidence"] in ("HIGH", "MEDIUM", "LOW")
    assert isinstance(data["strengths"], list)
    assert isinstance(data["gaps"], list)
    assert "dimensions" in data
    assert "strategy" in data


def test_analyze_endpoint_404(client):
    resp = client.post("/api/analyze", json={"job_id": 99999})
    assert resp.status_code == 404


def test_get_job_endpoint(client):
    """GET /jobs/{id} returns full description and 404 for missing."""
    from app.core.database import SessionLocal
    from app.models.job import Job

    db = SessionLocal()
    job = Job(title="Dev Intern", company="Corp", url="https://corp.com", description="Full JD text here.", source="test", content_hash="hash-corp-1")
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "Full JD text here."
    assert data["description_truncated"] is False

    resp404 = client.get("/jobs/99999")
    assert resp404.status_code == 404
