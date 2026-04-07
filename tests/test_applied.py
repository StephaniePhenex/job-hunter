"""PATCH /jobs/{id}/applied and job serialization."""

from app.models.job import Job
from app.services.dedupe import compute_content_hash
from app.utils.schemas import JobNormalized


def _make_job_row() -> Job:
    item = JobNormalized(
        title="Engineer",
        company="Acme",
        url="https://example.com/jobs/1",
        source="test",
    )
    ch = compute_content_hash(item)
    return Job(
        title=item.title,
        company=item.company,
        location="",
        url=item.url,
        description="",
        posted_at="",
        source=item.source,
        content_hash=ch,
        description_hash="x",
        tags=["backend"],
    )


def test_patch_applied_sets_timestamp(client) -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        j = _make_job_row()
        db.add(j)
        db.commit()
        db.refresh(j)
        job_id = j.id
    finally:
        db.close()

    r = client.patch(f"/jobs/{job_id}/applied", json={"applied": True})
    assert r.status_code == 200
    data = r.json()
    assert data["applied_at"] is not None
    assert data["tags"] == ["backend"]

    r2 = client.patch(f"/jobs/{job_id}/applied", json={"applied": False})
    assert r2.status_code == 200
    assert r2.json()["applied_at"] is None


def test_patch_applied_404(client) -> None:
    r = client.patch("/jobs/99999/applied", json={"applied": True})
    assert r.status_code == 404
