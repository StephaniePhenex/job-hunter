"""Dedupe hash behavior."""

from app.services.dedupe import compute_content_hash, compute_description_hash
from app.utils.schemas import JobNormalized


def test_content_hash_stable() -> None:
    a = JobNormalized(
        title=" SWE Intern ",
        company="Acme",
        url="https://example.com/jobs/1",
        source="test",
    )
    b = JobNormalized(
        title="swe intern",
        company="acme",
        url="https://example.com/jobs/1",
        source="test",
    )
    assert compute_content_hash(a) == compute_content_hash(b)


def test_description_change_changes_hash() -> None:
    assert compute_description_hash("a") != compute_description_hash("b")
