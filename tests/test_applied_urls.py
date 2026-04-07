"""Persistent applied state via ``applied_urls`` (survives full job table replace)."""

from app.core.database import SessionLocal
from app.models.applied_url import AppliedUrl
from app.models.job import Job
from app.services.dedupe import compute_content_hash
from app.utils.schemas import JobNormalized


def _insert_job(url: str = "https://example.com/apply/1") -> int:
    item = JobNormalized(
        title="Engineer",
        company="Acme",
        url=url,
        source="test",
    )
    ch = compute_content_hash(item)
    db = SessionLocal()
    try:
        j = Job(
            title=item.title,
            company=item.company,
            location="",
            url=item.url,
            description="",
            posted_at="",
            source=item.source,
            content_hash=ch,
            description_hash="x",
        )
        db.add(j)
        db.commit()
        db.refresh(j)
        return j.id
    finally:
        db.close()


def test_patch_creates_applied_url_row(client) -> None:
    job_id = _insert_job()
    r = client.patch(f"/jobs/{job_id}/applied", json={"applied": True})
    assert r.status_code == 200

    db = SessionLocal()
    try:
        rows = db.query(AppliedUrl).all()
        assert len(rows) == 1
        assert "example.com" in rows[0].url_norm
    finally:
        db.close()


def test_applied_survives_full_job_table_clear(client) -> None:
    url = "https://careers.example.com/jobs/99"
    job_id = _insert_job(url)
    assert client.patch(f"/jobs/{job_id}/applied", json={"applied": True}).status_code == 200

    item = JobNormalized(
        title="Engineer",
        company="Acme",
        url=url,
        source="test",
    )
    ch = compute_content_hash(item)

    db = SessionLocal()
    try:
        db.query(Job).delete(synchronize_session=False)
        db.commit()
        j2 = Job(
            title=item.title,
            company=item.company,
            location="SF",
            url=item.url,
            description="new desc",
            posted_at="",
            source=item.source,
            content_hash=ch,
            description_hash="newhash",
        )
        db.add(j2)
        db.commit()
    finally:
        db.close()

    r = client.get("/jobs")
    assert r.status_code == 200
    rows = [x for x in r.json()["items"] if x["url"] == url]
    assert len(rows) == 1
    assert rows[0]["applied_at"] is not None
