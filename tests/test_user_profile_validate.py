"""user_profile.yaml validation helper."""

from pathlib import Path

import pytest

from app.utils.user_profile_validate import validate_user_profile_yaml


def test_valid_default_repo_yaml() -> None:
    root = Path(__file__).resolve().parents[1]
    p = root / "user_profile.yaml"
    if not p.is_file():
        pytest.skip("user_profile.yaml not present")
    errors, warnings = validate_user_profile_yaml(p)
    assert not errors, errors


def test_invalid_regex_reports_error(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(
        """
profile:
  location_focus: "X"
  term: "t"
  interests: ["a"]
keywords:
  - label: "bad"
    regex: "[unclosed"
""",
        encoding="utf-8",
    )
    errors, _ = validate_user_profile_yaml(p)
    assert errors and any("invalid regex" in e.lower() for e in errors)


def test_empty_keywords_warns(tmp_path: Path) -> None:
    p = tmp_path / "empty.yaml"
    p.write_text("keywords: []\n", encoding="utf-8")
    errors, warnings = validate_user_profile_yaml(p)
    assert not errors
    assert any("no compilable" in w.lower() or "every job" in w.lower() for w in warnings)
