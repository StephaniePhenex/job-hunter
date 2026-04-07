"""Each full scan replaces the entire ``jobs`` table (no accumulation across runs)."""

from unittest.mock import patch

from app.agents.llm_client import ScoreResult
from app.core.database import SessionLocal
from app.models.job import Job
from app.services.dedupe import compute_content_hash
from app.services.pipeline import upsert_and_score_batch
from app.utils.schemas import JobNormalized


@patch("app.services.pipeline._score_many")
def test_scan_drops_previous_rows(mock_score) -> None:
    mock_score.return_value = [
        ScoreResult(match_score=0.6, priority="LOW", reason="ok", tags=[]),
    ]

    stale = JobNormalized(
        title="Community Policing",
        company="Old",
        url="https://example.com/stale",
        source="talentegg",
    )
    ch = compute_content_hash(stale)
    db = SessionLocal()
    try:
        db.add(
            Job(
                title=stale.title,
                company=stale.company,
                location="Canada",
                url=stale.url,
                description="",
                posted_at="",
                source=stale.source,
                content_hash=ch,
                description_hash="aa",
            )
        )
        db.commit()
    finally:
        db.close()

    incoming = JobNormalized(
        title="SWE Intern",
        company="Acme",
        url="https://example.com/new",
        description="build things",
        source="github",
    )
    db2 = SessionLocal()
    try:
        stats = upsert_and_score_batch(db2, [incoming])
    finally:
        db2.close()

    assert stats.get("cleared") == 1
    assert stats["new"] == 1

    db3 = SessionLocal()
    try:
        rows = db3.query(Job).all()
        assert len(rows) == 1
        assert rows[0].title == "SWE Intern"
    finally:
        db3.close()
