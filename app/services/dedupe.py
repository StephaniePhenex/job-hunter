"""Content hash and description change detection."""

import hashlib
from typing import Final

from app.utils.schemas import JobNormalized

_SEP: Final[str] = "\x1f"


def normalize_part(s: str) -> str:
    """Lowercase strip for stable hashing."""
    return " ".join(s.lower().split())


def compute_content_hash(job: JobNormalized) -> str:
    """SHA-256 of title + company + url (per spec)."""
    raw = _SEP.join(
        [
            normalize_part(job.title),
            normalize_part(job.company),
            job.url.strip(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_description_hash(description: str) -> str:
    """Hash full description text for update detection."""
    return hashlib.sha256(description.encode("utf-8")).hexdigest()
