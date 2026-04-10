"""Unified role keyword gate — loaded from user_profile.yaml.

Each keyword group in the YAML can use:
  terms: [...] — plain phrases compiled to a regex via re.escape + \\b anchors
  regex: "..."  — raw regex pattern (overrides terms)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from app.agents.llm_client import ScoreResult

logger = logging.getLogger(__name__)

_DEFAULT_YAML_PATH = Path(__file__).resolve().parents[2] / "user_profile.yaml"


def _load_focus_groups(path: Path) -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Compile keyword groups from user_profile.yaml into (label, pattern) tuples."""
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed; keyword filter disabled. Run: pip install pyyaml")
        return ()

    try:
        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.debug("user_profile.yaml not found at %s; keyword filter disabled", path)
        return ()
    except Exception:
        logger.exception("Failed to parse %s; keyword filter disabled", path)
        return ()

    groups: list[tuple[str, re.Pattern[str]]] = []
    for entry in data.get("keywords", []):
        label: str = entry.get("label", "")
        if not label:
            continue

        raw_regex: str | None = entry.get("regex")
        terms: list[str] = entry.get("terms", [])

        if raw_regex:
            # YAML >- folds newlines to spaces, producing "alt1| alt2" with spurious spaces
            # around the pipe operators. Collapse all whitespace first, then strip spaces
            # around | so alternations compile correctly regardless of YAML line wrapping.
            pattern_str = re.sub(r"\s+", " ", raw_regex).strip()
            pattern_str = re.sub(r"\s*\|\s*", "|", pattern_str)
        elif terms:
            pattern_str = "|".join(
                r"\b" + re.escape(t.strip()) + r"\b" for t in terms if t.strip()
            )
        else:
            continue

        try:
            groups.append((label, re.compile(pattern_str, re.IGNORECASE | re.DOTALL)))
        except re.error as exc:
            logger.error("Bad regex for keyword group %r: %s", label, exc)

    return tuple(groups)


_FOCUS_GROUPS: tuple[tuple[str, re.Pattern[str]], ...] = _load_focus_groups(_DEFAULT_YAML_PATH)
FOCUS_GROUP_TOTAL = len(_FOCUS_GROUPS)


def _combined_blob(title: str, company: str, description: str) -> str:
    return f"{title}\n{company}\n{description}"


def focus_group_labels_matched(
    title: str = "",
    company: str = "",
    description: str = "",
) -> list[str]:
    """Labels for each keyword group that matches (same order as YAML)."""
    blob = _combined_blob(title, company, description)
    if not blob.strip():
        return []
    return [label for label, rx in _FOCUS_GROUPS if rx.search(blob)]


def count_focus_group_hits(title: str = "", company: str = "", description: str = "") -> int:
    """How many distinct keyword groups match."""
    return len(focus_group_labels_matched(title, company, description))


def priority_from_focus_group_hits(hit_count: int) -> Literal["HIGH", "MEDIUM", "LOW"]:
    """Map keyword-group hit count to priority (sole source of HIGH/MEDIUM/LOW tiers)."""
    if hit_count <= 1:
        return "LOW"
    if hit_count <= 3:
        return "MEDIUM"
    return "HIGH"


def passes_focus_role_keywords(
    title: str = "",
    company: str = "",
    description: str = "",
) -> bool:
    """Return True if combined text matches at least one focus role keyword group."""
    return count_focus_group_hits(title, company, description) > 0


def merged_focus_and_llm_tags(
    llm_tags: list[str] | None,
    title: str,
    company: str,
    description: str,
    max_tags: int = 16,
) -> list[str]:
    """Keyword group labels first, then LLM tags, de-duplicated case-insensitively."""
    kw = focus_group_labels_matched(title, company, description)
    seen: set[str] = set()
    out: list[str] = []
    for t in kw + (llm_tags or []):
        s = (t or "").strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max_tags:
            break
    return out


def merge_llm_score_with_keyword_priority(
    score: ScoreResult,
    title: str,
    company: str,
    description: str,
) -> tuple[ScoreResult, Literal["HIGH", "MEDIUM", "LOW"]]:
    """Set priority from keyword-group hits only; prefix reason with hit counts."""
    n = count_focus_group_hits(title, company, description)
    pri = priority_from_focus_group_hits(n)
    prefix = f"[{n}/{FOCUS_GROUP_TOTAL} groups] "
    new_reason = (prefix + (score.reason or "")).strip()[:1024]
    updated = score.model_copy(update={"reason": new_reason})
    return updated, pri
