"""SQLAlchemy models."""

from app.models.applied_url import AppliedUrl
from app.models.job import Job
from app.models.job_analysis import JobAnalysis

__all__ = ["AppliedUrl", "Job", "JobAnalysis"]
