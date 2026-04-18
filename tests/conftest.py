"""Test DB: isolated SQLite file + clean schema between tests."""

import os
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'pytest.db'}"
# Deterministic Analyze/Optimize; do not call real LLMs in CI or dev machines with keys set.
os.environ["ANALYZE_USE_MOCK"] = "true"
os.environ["OPTIMIZE_USE_MOCK"] = "true"

from app.core.database import Base, engine  # noqa: E402
from app.core.schema_upgrade import upgrade_job_table  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    upgrade_job_table(engine)
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
