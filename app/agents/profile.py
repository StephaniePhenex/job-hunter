"""User profile for relevance scoring — loaded from user_profile.yaml."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_DEFAULT_YAML_PATH = Path(__file__).resolve().parents[2] / "user_profile.yaml"


class UserProfile(BaseModel):
    """Target intern seeker preferences passed to the LLM for scoring."""

    location_focus: str = Field(default="Canada", description="Geographic focus")
    term: str = Field(default="Fall internship", description="Preferred internship term")
    interests: list[str] = Field(
        default_factory=lambda: [
            "Web3",
            "Software engineering",
            "Media / content",
            "Tech + culture intersection",
        ]
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # PyYAML (already in requirements via pydantic-settings extras or explicit)
    except ImportError:
        logger.warning("PyYAML not installed; using default profile. Run: pip install pyyaml")
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.debug("user_profile.yaml not found at %s; using defaults", path)
        return {}
    except Exception:
        logger.exception("Failed to parse %s; using defaults", path)
        return {}


def load_user_profile(path: Path | None = None) -> UserProfile:
    """Load UserProfile from YAML. Falls back to defaults on any error."""
    resolved = path or _DEFAULT_YAML_PATH
    data = _load_yaml(resolved)
    raw = data.get("profile", {})
    if not raw:
        return UserProfile()
    return UserProfile.model_validate(raw)


DEFAULT_USER_PROFILE = load_user_profile()
