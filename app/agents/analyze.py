"""Agentic Bridge — deep match analysis for a single job posting.

Data flow (per plan):
  LLM → JSON → Pydantic (AnalyzeResult) → Deterministic Guard → API response
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.agents.profile import UserProfile
from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ─── Schema ───────────────────────────────────────────────────────────────────

class AnalyzeDimensions(BaseModel):
    hard_skills: int = Field(ge=0, le=100)
    experience: int = Field(ge=0, le=100)
    synergy: int = Field(ge=0, le=100)


class AnalyzeStrategy(BaseModel):
    focus: str = Field(max_length=64)
    key_message: str = Field(max_length=512)
    risk: str = Field(max_length=256)


class AnalyzeResult(BaseModel):
    score: int = Field(ge=0, le=100)
    dimensions: AnalyzeDimensions
    decision: Literal["APPLY", "SKIP", "STRETCH"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    strengths: list[str]
    gaps: list[str]
    recommended_resume_id: str = ""
    recommended_resume_reason: str = ""   # optional: why this resume was chosen
    strategy: AnalyzeStrategy
    # Guard audit fields (included in response for debugging)
    guard_adjusted: bool = False
    guard_notes: list[str] = Field(default_factory=list)

    @field_validator("strengths")
    @classmethod
    def _cap_strengths(cls, v: list[str]) -> list[str]:
        return v[:3]

    @field_validator("gaps")
    @classmethod
    def _cap_gaps(cls, v: list[str]) -> list[str]:
        return v[:2]


# ─── Deterministic Guard ──────────────────────────────────────────────────────

def apply_guard(result: AnalyzeResult, valid_resume_ids: list[str]) -> AnalyzeResult:
    """Apply deterministic corrections after Pydantic validation.

    Rules (thresholds configurable via settings in future):
      1. gaps>=2 AND score>85  → cap score to 80
      2. score<65 AND decision==APPLY  → downgrade to STRETCH
      3. score<40 AND decision in (APPLY, STRETCH)  → downgrade to SKIP
      4. recommended_resume_id not in valid_resume_ids  → fallback to first id
    """
    score = result.score
    decision = result.decision
    resume_id = result.recommended_resume_id
    notes: list[str] = []

    if len(result.gaps) >= 2 and score > 85:
        notes.append(f"score capped {score}→80 (gaps≥2 with score>85)")
        score = 80

    if score < 65 and decision == "APPLY":
        notes.append(f"decision APPLY→STRETCH (score={score}<65)")
        decision = "STRETCH"

    if score < 40 and decision in ("APPLY", "STRETCH"):
        notes.append(f"decision {decision}→SKIP (score={score}<40)")
        decision = "SKIP"

    if valid_resume_ids and resume_id not in valid_resume_ids:
        fallback = valid_resume_ids[0]
        notes.append(f"resume_id '{resume_id}' invalid → fallback to '{fallback}'")
        resume_id = fallback

    if notes:
        return result.model_copy(update={
            "score": score,
            "decision": decision,
            "recommended_resume_id": resume_id,
            "guard_adjusted": True,
            "guard_notes": notes,
        })

    return result


# ─── Mock result ──────────────────────────────────────────────────────────────

_MOCK_RESULT = AnalyzeResult(
    score=72,
    dimensions=AnalyzeDimensions(hard_skills=75, experience=65, synergy=80),
    decision="APPLY",
    confidence="MEDIUM",
    strengths=[
        "Full-stack background (React + FastAPI) maps directly to the role's core requirements.",
        "Research and podcast experience offers rare synergy for media-adjacent or product roles.",
        "ROS 2 / CV work demonstrates low-level systems depth beyond typical web applicants.",
    ],
    gaps=[
        "Limited production-scale cloud infra experience (AWS/GCP at depth).",
    ],
    recommended_resume_id="",
    strategy=AnalyzeStrategy(
        focus="fullstack",
        key_message=(
            "Lead with cross-disciplinary depth: engineering + research + media "
            "creates a differentiated signal in a generalist role."
        ),
        risk="May need to reframe academic timeline as deliberate breadth, not slow delivery.",
    ),
)


# ─── LLM call (D4) ───────────────────────────────────────────────────────────

def _parse_analyze_json(text: str) -> AnalyzeResult:
    data = json.loads(text)
    # Normalize: LLM may return 0-1 floats instead of 0-100 ints
    def _to_int100(v) -> int:
        if isinstance(v, float) and 0.0 <= v <= 1.0:
            return round(v * 100)
        return int(v)

    if "score" in data:
        data["score"] = _to_int100(data["score"])
    if "dimensions" in data:
        for k in ("hard_skills", "experience", "synergy"):
            if k in data["dimensions"]:
                data["dimensions"][k] = _to_int100(data["dimensions"][k])
    # Truncate strategy fields to schema limits (LLMs often exceed max_length)
    if "strategy" in data and isinstance(data["strategy"], dict):
        s = data["strategy"]
        if "focus" in s and isinstance(s["focus"], str) and len(s["focus"]) > 64:
            s["focus"] = s["focus"][:64]
        if "key_message" in s and isinstance(s["key_message"], str) and len(s["key_message"]) > 512:
            s["key_message"] = s["key_message"][:512]
        if "risk" in s and isinstance(s["risk"], str) and len(s["risk"]) > 256:
            s["risk"] = s["risk"][:256]
    return AnalyzeResult.model_validate(data)


def _analyze_gemini(
    description: str,
    profile: UserProfile,
    resumes: list[dict],
    system_prompt: str,
    user_prompt: str,
) -> AnalyzeResult:
    import google.generativeai as genai

    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        settings.gemini_model,
        system_instruction=system_prompt,
    )
    resp = model.generate_content(
        user_prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
        request_options={"timeout": 60},
    )
    text = (resp.text or "").strip() or "{}"
    return _parse_analyze_json(text)


def _analyze_openai(
    description: str,
    profile: UserProfile,
    resumes: list[dict],
    system_prompt: str,
    user_prompt: str,
) -> AnalyzeResult:
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key, timeout=60.0)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    text = resp.choices[0].message.content or "{}"
    return _parse_analyze_json(text)


def analyze_job_llm(
    title: str,
    company: str,
    description: str,
    profile: UserProfile,
    resumes: list[dict] | None = None,
) -> AnalyzeResult:
    """Call LLM for deep analysis. One retry on JSON parse failure."""
    from app.agents.analyze_prompt import build_prompts

    resumes = resumes or []
    system_prompt, user_prompt = build_prompts(
        job_description=description[:12000],
        title=title,
        company=company,
        user_profile=profile,
        resumes=resumes,
    )
    settings = get_settings()

    def _call() -> AnalyzeResult:
        if settings.gemini_api_key:
            return _analyze_gemini(description, profile, resumes, system_prompt, user_prompt)
        if settings.openai_api_key:
            return _analyze_openai(description, profile, resumes, system_prompt, user_prompt)
        raise RuntimeError("No LLM API key configured (set GEMINI_API_KEY or OPENAI_API_KEY)")

    for attempt in range(2):
        try:
            return _call()
        except Exception as exc:
            if attempt == 0:
                logger.warning("analyze_job_llm attempt 1 failed (%s), retrying", exc)
            else:
                logger.exception("analyze_job_llm failed after 2 attempts")
                raise
    raise RuntimeError("unreachable")
