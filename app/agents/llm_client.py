"""LLM abstraction: structured job relevance scoring (Gemini or OpenAI)."""

import json
import logging
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents.profile import UserProfile
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")

_SYSTEM_PROMPT = (
    "You are a recruiting assistant. Score how well an internship matches the user profile. "
    "Respond with a single JSON object only, no markdown, with keys: "
    "match_score (number from 0 to 1), "
    "reason (short string), "
    "tags (array of strings, max 8): choose zero or more topic labels from this set when relevant: "
    "web3, backend, frontend, data, mobile, devops, media, product, research, other. "
    "Use lowercase slug form (e.g. backend). Omit tags if none apply. "
    "Do not include priority or importance tiers; relevance ranking is applied separately."
)


class ScoreResult(BaseModel):
    """Structured LLM output (match/reason/tags only). Priority is computed in-app from keywords."""

    model_config = ConfigDict(extra="ignore")

    match_score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(max_length=1024)
    tags: list[str] = Field(
        default_factory=list,
        description="Topic labels, lowercase slugs (e.g. web3, backend, media).",
    )

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            return []
        out: list[str] = []
        for x in v[:8]:
            if not isinstance(x, str):
                continue
            s = x.strip().lower().replace(" ", "_")
            if s and _TAG_RE.match(s):
                out.append(s)
        return list(dict.fromkeys(out))


def _no_key_result() -> ScoreResult:
    return ScoreResult(
        match_score=0.0,
        reason="No LLM API key configured (set GEMINI_API_KEY or OPENAI_API_KEY).",
        tags=[],
    )


def _parse_score_json(text: str) -> ScoreResult:
    data = json.loads(text)
    if "tags" not in data:
        data["tags"] = []
    # Legacy LLM responses may still include priority; ignored via model_config extra="ignore".
    return ScoreResult.model_validate(data)


def _score_gemini(
    description: str,
    title: str,
    company: str,
    profile: UserProfile,
) -> ScoreResult:
    import google.generativeai as genai

    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    user_payload = {
        "profile": profile.model_dump(),
        "job": {
            "title": title,
            "company": company,
            "description": description[:12000],
        },
    }
    user = json.dumps(user_payload, ensure_ascii=False)

    model = genai.GenerativeModel(
        settings.gemini_model,
        system_instruction=_SYSTEM_PROMPT,
    )
    resp = model.generate_content(
        user,
        generation_config=genai.GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
        request_options={"timeout": 60},
    )
    text = (resp.text or "").strip() or "{}"
    return _parse_score_json(text)


def _score_openai(
    description: str,
    title: str,
    company: str,
    profile: UserProfile,
) -> ScoreResult:
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key, timeout=60.0)
    user_payload = {
        "profile": profile.model_dump(),
        "job": {
            "title": title,
            "company": company,
            "description": description[:12000],
        },
    }
    user = json.dumps(user_payload, ensure_ascii=False)

    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    text = resp.choices[0].message.content or "{}"
    return _parse_score_json(text)


def score_job(description: str, title: str, company: str, profile: UserProfile) -> ScoreResult:
    """Call Gemini (preferred) or OpenAI for JSON scoring; fallback to LOW on failure."""
    settings = get_settings()

    if settings.gemini_api_key:
        try:
            return _score_gemini(description, title, company, profile)
        except Exception:
            logger.exception("Gemini scoring failed; using LOW fallback")
            return ScoreResult(
                match_score=0.0,
                reason="Scoring failed; check logs.",
                tags=[],
            )

    if settings.openai_api_key:
        try:
            return _score_openai(description, title, company, profile)
        except Exception:
            logger.exception("OpenAI scoring failed; using LOW fallback")
            return ScoreResult(
                match_score=0.0,
                reason="Scoring failed; check logs.",
                tags=[],
            )

    logger.warning("No GEMINI_API_KEY or OPENAI_API_KEY; returning default LOW score")
    return _no_key_result()
