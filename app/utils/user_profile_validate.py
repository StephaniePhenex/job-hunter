"""Validate ``user_profile.yaml`` before restart (keywords compile + optional profile)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.agents.profile import UserProfile


def validate_user_profile_yaml(path: Path) -> tuple[list[str], list[str]]:
    """Load and check ``user_profile.yaml``.

    Returns:
        ``errors`` — must be empty for a safe run (broken regex, invalid profile, etc.).
        ``warnings`` — e.g. empty ``keywords`` (pipeline would drop every job).

    Mirrors compilation rules in ``app.utils.role_keywords._load_focus_groups``.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        import yaml
    except ImportError as e:
        return [f"PyYAML is required: {e}"], []

    if not path.is_file():
        return [f"File not found: {path}"], []

    try:
        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except Exception as e:
        return [f"YAML parse error: {e}"], []

    # --- profile (LLM scoring) ---
    raw_profile = data.get("profile")
    if raw_profile is not None and raw_profile != {}:
        try:
            UserProfile.model_validate(raw_profile)
        except Exception as e:
            errors.append(f"Invalid `profile:` section: {e}")

    # --- keywords ---
    raw_kw = data.get("keywords")
    if raw_kw is None:
        warnings.append("Missing `keywords:` key — no filter groups (every job would be dropped).")
        return errors, warnings
    if not isinstance(raw_kw, list):
        errors.append("`keywords` must be a list of mapping entries.")
        return errors, warnings

    compiled = 0
    for i, entry in enumerate(raw_kw):
        if not isinstance(entry, dict):
            errors.append(f"keywords[{i}] must be a mapping, got {type(entry).__name__}.")
            continue
        label = (entry.get("label") or "").strip()
        raw_regex = entry.get("regex")
        terms = entry.get("terms", [])

        if not label:
            warnings.append(f"keywords[{i}]: skipped (empty `label`).")
            continue

        if raw_regex:
            pattern_str = re.sub(r"\s+", " ", str(raw_regex)).strip()
        elif isinstance(terms, list) and terms:
            parts = [t.strip() for t in terms if isinstance(t, str) and t.strip()]
            if not parts:
                warnings.append(f"keywords[{i}] ({label!r}): skipped (empty `terms`).")
                continue
            pattern_str = "|".join(r"\b" + re.escape(t) + r"\b" for t in parts)
        else:
            warnings.append(f"keywords[{i}] ({label!r}): skipped (need `terms` or `regex`).")
            continue

        try:
            re.compile(pattern_str, re.IGNORECASE | re.DOTALL)
        except re.error as exc:
            errors.append(f"keywords[{i}] ({label!r}): invalid regex: {exc}")
            continue
        compiled += 1

    if compiled == 0:
        warnings.append(
            "No compilable keyword groups — `passes_focus_role_keywords` will reject all jobs."
        )

    return errors, warnings
