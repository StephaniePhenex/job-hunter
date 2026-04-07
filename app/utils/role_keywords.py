"""Unified role keyword gate for all job sources.

Aligned with product focus: builder / creator / AI+SaaS full-stack, Web3, media & entertainment
architecture, DevRel, creative tech, digital assets, UX/front-end product engineering, etc.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.agents.llm_client import ScoreResult

# Each entry: (human-readable chip label, regex). Order is stable for display.
_FOCUS_GROUPS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "Full-stack AI/SaaS",
        re.compile(
            r"full[\s-]*stack.{0,80}(ai|saas|sa\s*a\s*s)|\(ai\s*/\s*saas\)|"
            r"(ai|saas).{0,50}full[\s-]*stack|full[\s-]*stack\s+engineer.{0,60}(ai|saas)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "AI builder",
        re.compile(r"\b(ai|artificial\s+intelligence)\s*builder\b", re.IGNORECASE),
    ),
    (
        "Product builder",
        re.compile(r"\bproduct\s*builder\b", re.IGNORECASE),
    ),
    (
        "Creator tools",
        re.compile(
            r"creator\s*tools|software\s*engineer.{0,50}creator|creator.{0,50}software\s*engineer",
            re.IGNORECASE,
        ),
    ),
    (
        "Product engineer",
        re.compile(r"\bproduct\s*engineer\b", re.IGNORECASE),
    ),
    (
        "Software engineer",
        re.compile(r"\bsoftware\s*engineer\b", re.IGNORECASE),
    ),
    (
        "Full-stack engineer",
        re.compile(r"\bfull[\s-]*stack\s*engineer\b", re.IGNORECASE),
    ),
    (
        "Technical Content Engineer",
        re.compile(r"technical\s*content\s*engineer", re.IGNORECASE),
    ),
    (
        "MLOps / AI implementation",
        re.compile(
            r"\bmlops\b|\bml\s+ops\b|ai\s+implementation\s+engineer|"
            r"mlops\s*/\s*ai|ai\s*/\s*mlops",
            re.IGNORECASE,
        ),
    ),
    (
        "UX engineer",
        re.compile(r"\bux\s*engineer\b|u\.x\.\s*engineer", re.IGNORECASE),
    ),
    (
        "Front-end / UI",
        re.compile(
            r"front[\s-]*end\s*engineer|frontend\s*engineer|"
            r"(front[\s-]*end|frontend|ui).{0,40}engineer.{0,40}ui|ui\s*focus",
            re.IGNORECASE,
        ),
    ),
    ("Web3", re.compile(r"\bweb3\b", re.IGNORECASE)),
    (
        "Web3 full-stack",
        re.compile(
            r"web3.{0,80}full[\s-]*stack|full[\s-]*stack.{0,80}web3",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "Architect (media)",
        re.compile(
            r"solution\s*architect.{0,120}(media|entertainment)|"
            r"(media\s*&\s*entertainment|media\s+and\s+entertainment).{0,80}solution\s*architect|"
            r"solution\s*architect.{0,120}(media\s*&|entertainment)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "DevRel",
        re.compile(r"\bdevrel\b|developer\s*relations", re.IGNORECASE),
    ),
    (
        "Creative technologist",
        re.compile(r"creative\s*technologist", re.IGNORECASE),
    ),
    (
        "Media engineer",
        re.compile(r"media\s*engineer", re.IGNORECASE),
    ),
    (
        "Digital assets",
        re.compile(
            r"digital\s*assets?\s*develop\w*|develop\w*.{0,30}digital\s*assets?",
            re.IGNORECASE,
        ),
    ),
    # Explicit product allowlist (games/media/marketing/engineering internships)
    (
        "Animation / VFX (games)",
        re.compile(
            r"\bvfx\b|"
            r"\banimation\b.{0,70}(games?|intern|studio|sledgehammer)|"
            r"sledgehammer\s+games|"
            r"intern(ship)?.{0,30}\b(vfx|animation)\b|\b(vfx|animation)\b.{0,40}intern",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "Digital marketing / Journalism",
        re.compile(
            r"journalism\s+and\s+digital\s+marketing|"
            r"\bdigital\s+marketing\b.{0,100}\bintern(ship)?\b|"
            r"\bintern(ship)?.{0,100}\bdigital\s+marketing\b|"
            r"marketing,\s*rpm\s+internship",
            re.IGNORECASE,
        ),
    ),
    (
        "Electrical engineering",
        re.compile(
            r"\belectrical\s+engineering\b.{0,50}\bintern(ship)?\b|"
            r"\bintern(ship)?.{0,50}\belectrical\s+engineering\b",
            re.IGNORECASE,
        ),
    ),
)

FOCUS_GROUP_TOTAL = len(_FOCUS_GROUPS)


def _combined_blob(title: str, company: str, description: str) -> str:
    return f"{title}\n{company}\n{description}"


def focus_group_labels_matched(
    title: str = "",
    company: str = "",
    description: str = "",
) -> list[str]:
    """Labels for each keyword group that matches (same order as _FOCUS_GROUPS)."""
    blob = _combined_blob(title, company, description)
    if not blob.strip():
        return []
    return [label for label, rx in _FOCUS_GROUPS if rx.search(blob)]


def count_focus_group_hits(title: str = "", company: str = "", description: str = "") -> int:
    """How many distinct keyword groups match."""
    return len(focus_group_labels_matched(title, company, description))


def priority_from_focus_group_hits(hit_count: int) -> Literal["HIGH", "MEDIUM", "LOW"]:
    """Map keyword-group hit count to priority (overrides LLM tier)."""
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
    """Return True if combined text matches at least one focus role keyword cluster."""
    return count_focus_group_hits(title, company, description) > 0


def merged_focus_and_llm_tags(
    llm_tags: list[str] | None,
    title: str,
    company: str,
    description: str,
    max_tags: int = 16,
) -> list[str]:
    """Keyword group labels first, then LLM tags, de-duplicated by case-insensitive string."""
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
) -> ScoreResult:
    """Override LLM priority using keyword-group hits; annotate reason (tags merged in pipeline)."""
    n = count_focus_group_hits(title, company, description)
    pri = priority_from_focus_group_hits(n)
    prefix = f"[{n}/{FOCUS_GROUP_TOTAL} groups] "
    new_reason = (prefix + (score.reason or "")).strip()[:1024]
    return score.model_copy(update={"priority": pri, "reason": new_reason})
