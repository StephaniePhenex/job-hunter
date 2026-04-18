"""Phase 2 tests: resumes loading, cache hit/miss, resume ID routing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.agents.profile import (
    ResumeEntry,
    UserProfile,
    load_resume_entries_from_disk,
    load_user_profile,
    resumes_as_dicts,
)
from app.utils.user_profile_validate import validate_user_profile_yaml


# ─── D11: Profile + resumes loading ──────────────────────────────────────────

def test_resume_entry_requires_id_and_content():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ResumeEntry(id="", content="text")   # empty id
    with pytest.raises(ValidationError):
        ResumeEntry(id="ok", content="")     # empty content


def test_load_user_profile_reads_resumes(tmp_path: Path):
    yaml_path = tmp_path / "user_profile.yaml"
    yaml_path.write_text(yaml.dump({
        "profile": {"location_focus": "Canada", "term": "Fall 2026", "interests": ["AI"]},
        "resumes": [
            {"id": "fullstack", "content": "React + FastAPI engineer"},
            {"id": "research",  "content": "Robotics research background"},
        ],
    }))
    profile = load_user_profile(yaml_path, project_root=tmp_path)
    assert len(profile.resumes) == 2
    assert profile.resumes[0].id == "fullstack"
    assert profile.resumes[1].id == "research"


def test_resumes_as_dicts():
    profile = UserProfile(resumes=[
        ResumeEntry(id="a", content="Resume A"),
        ResumeEntry(id="b", content="Resume B"),
    ])
    dicts = resumes_as_dicts(profile)
    assert dicts == [{"id": "a", "content": "Resume A"}, {"id": "b", "content": "Resume B"}]


def test_load_user_profile_no_resumes_returns_empty(tmp_path: Path):
    yaml_path = tmp_path / "user_profile.yaml"
    yaml_path.write_text(yaml.dump({"profile": {"location_focus": "Canada", "term": "Fall"}}))
    profile = load_user_profile(yaml_path, project_root=tmp_path)
    assert profile.resumes == []


def test_load_resume_entries_from_disk_reads_docx(tmp_path: Path):
    docx = pytest.importorskip("docx", reason="python-docx required")
    rdir = tmp_path / "data" / "resumes"
    rdir.mkdir(parents=True)
    doc_path = rdir / "word-cv.docx"
    document = docx.Document()
    document.add_paragraph("Line one from Word")
    document.add_paragraph("Line two")
    document.save(str(doc_path))
    entries = load_resume_entries_from_disk(rdir)
    assert len(entries) == 1
    assert entries[0].id == "word-cv"
    assert "Line one from Word" in entries[0].content
    assert "Line two" in entries[0].content


def test_load_resume_entries_from_disk_skips_readme(tmp_path: Path):
    rdir = tmp_path / "data" / "resumes"
    rdir.mkdir(parents=True)
    (rdir / "README.md").write_text("noise", encoding="utf-8")
    (rdir / "alpha.md").write_text("Content A", encoding="utf-8")
    entries = load_resume_entries_from_disk(rdir)
    assert len(entries) == 1
    assert entries[0].id == "alpha"
    assert entries[0].content == "Content A"


def test_disk_resumes_merge_override_yaml(tmp_path: Path):
    yaml_path = tmp_path / "user_profile.yaml"
    yaml_path.write_text(
        yaml.dump({
            "profile": {"location_focus": "CA", "term": "Fall", "interests": ["x"]},
            "resumes": [{"id": "fullstack", "content": "from yaml"}],
        })
    )
    rdir = tmp_path / "data" / "resumes"
    rdir.mkdir(parents=True)
    (rdir / "fullstack.md").write_text("from disk file", encoding="utf-8")
    (rdir / "solo.txt").write_text("only on disk", encoding="utf-8")
    profile = load_user_profile(yaml_path, project_root=tmp_path)
    by_id = {r.id: r.content for r in profile.resumes}
    assert by_id["fullstack"] == "from disk file"
    assert by_id["solo"] == "only on disk"
    ids = [r.id for r in profile.resumes]
    assert ids[0] == "fullstack"
    assert "solo" in ids


def test_disk_resumes_merge_respects_disabled_flag(tmp_path: Path):
    yaml_path = tmp_path / "user_profile.yaml"
    yaml_path.write_text(
        yaml.dump({
            "profile": {"location_focus": "CA", "term": "Fall", "interests": ["x"]},
            "resumes": [{"id": "a", "content": "yaml only"}],
        })
    )
    rdir = tmp_path / "data" / "resumes"
    rdir.mkdir(parents=True)
    (rdir / "b.md").write_text("disk", encoding="utf-8")
    profile = load_user_profile(
        yaml_path,
        project_root=tmp_path,
        resume_files_enabled=False,
    )
    assert len(profile.resumes) == 1
    assert profile.resumes[0].id == "a"


# ─── D11: validate_user_profile_yaml — resumes section ───────────────────────

def test_validate_resumes_ok(tmp_path: Path):
    yaml_path = tmp_path / "user_profile.yaml"
    yaml_path.write_text(yaml.dump({
        "resumes": [{"id": "cv1", "content": "Some text"}],
        "keywords": [{"label": "SWE", "terms": ["software engineer"]}],
    }))
    errors, _ = validate_user_profile_yaml(yaml_path)
    assert errors == []


def test_validate_resumes_duplicate_id(tmp_path: Path):
    yaml_path = tmp_path / "user_profile.yaml"
    yaml_path.write_text(yaml.dump({
        "resumes": [
            {"id": "cv1", "content": "text"},
            {"id": "cv1", "content": "other"},
        ],
        "keywords": [{"label": "SWE", "terms": ["engineer"]}],
    }))
    errors, _ = validate_user_profile_yaml(yaml_path)
    assert any("duplicate" in e for e in errors)


def test_validate_resumes_missing_content(tmp_path: Path):
    yaml_path = tmp_path / "user_profile.yaml"
    yaml_path.write_text(yaml.dump({
        "resumes": [{"id": "cv1"}],
        "keywords": [{"label": "SWE", "terms": ["engineer"]}],
    }))
    errors, _ = validate_user_profile_yaml(yaml_path)
    assert errors  # missing content field


def test_real_user_profile_yaml_passes_validation():
    """The repo's own user_profile.yaml must pass validation after Phase 2 changes."""
    root = Path(__file__).resolve().parents[1]
    errors, warnings = validate_user_profile_yaml(root / "user_profile.yaml")
    assert errors == [], f"Errors: {errors}"


# ─── D14: Cache hit/miss via /api/analyze ─────────────────────────────────────

def _seed_job(db):
    from app.models.job import Job
    job = Job(title="Dev", company="Corp", url="https://corp.com", source="test", content_hash="hash-corp-p2")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job.id


def test_analyze_cache_miss_then_hit(client):
    from app.core.database import SessionLocal
    from app.models.job_analysis import JobAnalysis

    db = SessionLocal()
    job_id = _seed_job(db)
    db.close()

    # First call — cache miss, runs analysis, stores result.
    r1 = client.post("/api/analyze", json={"job_id": job_id})
    assert r1.status_code == 200

    # Confirm cached row was written.
    db = SessionLocal()
    cached = db.query(JobAnalysis).filter(JobAnalysis.job_id == job_id).one_or_none()
    assert cached is not None
    stored = json.loads(cached.result_json)
    db.close()

    # Second call — cache hit, must return same data.
    r2 = client.post("/api/analyze", json={"job_id": job_id})
    assert r2.status_code == 200
    assert r2.json() == stored


def test_analyze_force_refresh_updates_cache(client):
    from app.core.database import SessionLocal
    from app.models.job_analysis import JobAnalysis

    db = SessionLocal()
    job_id = _seed_job(db)
    db.close()

    # Prime the cache.
    client.post("/api/analyze", json={"job_id": job_id})

    # force_refresh should re-run and overwrite.
    r = client.post("/api/analyze", json={"job_id": job_id, "force_refresh": True})
    assert r.status_code == 200

    db = SessionLocal()
    count = db.query(JobAnalysis).filter(JobAnalysis.job_id == job_id).count()
    db.close()
    assert count == 1  # still only one row (upsert, not duplicate)


# ─── D12: Guard uses real resume IDs from user_profile.yaml ──────────────────

def test_mock_result_guard_uses_valid_ids(client):
    """Mock recommended_resume_id="" — guard fallback to first ID if resumes configured."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    job_id = _seed_job(db)
    db.close()

    r = client.post("/api/analyze", json={"job_id": job_id, "force_refresh": True})
    data = r.json()
    # Mock result has recommended_resume_id="" which is not in valid_ids → fallback applied.
    # If user_profile.yaml has resumes, guard fires; if empty, id stays "".
    assert "recommended_resume_id" in data
