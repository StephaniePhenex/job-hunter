"""Optimize agent: Writer → Critic pipeline.

Data flow:
  Writer LLM (plain text) → Critic LLM (JSON) → OptimizeResult
  Streaming variant yields SSE strings for the /api/optimize/stream endpoint.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from typing import Any

from pydantic import BaseModel, Field

from app.agents.optimize_prompt import build_critic_prompts, build_writer_prompts
from app.agents.profile import ResumeEntry, UserProfile
from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ─── Result schemas ───────────────────────────────────────────────────────────

class CriticResult(BaseModel):
    approved: bool
    notes: str = ""
    violations: list[str] = Field(default_factory=list)


class OptimizeResult(BaseModel):
    resume_id: str
    original: str
    optimized: str
    critic_approved: bool
    critic_notes: str
    violations: list[str]


# ─── Mock results ─────────────────────────────────────────────────────────────

def _mock_optimize(resume_entry: ResumeEntry, title: str, company: str) -> OptimizeResult:
    optimized = (
        f"[MOCK — optimized for {title} @ {company}]\n\n"
        + resume_entry.content.strip()
        + "\n\n• Highlighted relevant experience for this role.\n• Emphasised transferable skills."
    )
    return OptimizeResult(
        resume_id=resume_entry.id,
        original=resume_entry.content,
        optimized=optimized,
        critic_approved=True,
        critic_notes="Mock review: no violations detected.",
        violations=[],
    )


# ─── LLM helpers ─────────────────────────────────────────────────────────────

def _call_gemini_text(system: str, user: str) -> str:
    import google.generativeai as genai
    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model, system_instruction=system)
    resp = model.generate_content(user, request_options={"timeout": 90})
    return (resp.text or "").strip()


def _call_openai_text(system: str, user: str) -> str:
    from openai import OpenAI
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key, timeout=90.0)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""


def _call_gemini_json(system: str, user: str) -> dict[str, Any]:
    import google.generativeai as genai
    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model, system_instruction=system)
    resp = model.generate_content(
        user,
        generation_config=genai.GenerationConfig(temperature=0.1, response_mime_type="application/json"),
        request_options={"timeout": 60},
    )
    return json.loads((resp.text or "{}").strip())


def _call_openai_json(system: str, user: str) -> dict[str, Any]:
    from openai import OpenAI
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key, timeout=60.0)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(resp.choices[0].message.content or "{}")


def _writer_call(system: str, user: str) -> str:
    settings = get_settings()
    if settings.gemini_api_key:
        return _call_gemini_text(system, user)
    if settings.openai_api_key:
        return _call_openai_text(system, user)
    raise RuntimeError("No LLM API key configured")


def _critic_call(system: str, user: str) -> CriticResult:
    settings = get_settings()
    try:
        if settings.gemini_api_key:
            raw = _call_gemini_json(system, user)
        elif settings.openai_api_key:
            raw = _call_openai_json(system, user)
        else:
            raise RuntimeError("No LLM API key configured")
        return CriticResult.model_validate(raw)
    except Exception as exc:
        logger.warning("Critic LLM failed (%s); returning safe default", exc)
        return CriticResult(approved=False, notes=f"Critic failed: {exc}", violations=[])


# ─── Streaming helpers ────────────────────────────────────────────────────────

def _stream_gemini_text(system: str, user: str) -> Generator[str, None, None]:
    import google.generativeai as genai
    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model, system_instruction=system)
    for chunk in model.generate_content(user, stream=True, request_options={"timeout": 90}):
        if chunk.text:
            yield chunk.text


def _stream_openai_text(system: str, user: str) -> Generator[str, None, None]:
    from openai import OpenAI
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key, timeout=90.0)
    for chunk in client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
        stream=True,
    ):
        text = chunk.choices[0].delta.content
        if text:
            yield text


def _sse(data: dict[str, Any]) -> str:
    """Format one SSE message."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ─── Public API ───────────────────────────────────────────────────────────────

def optimize_resume(
    title: str,
    company: str,
    job_description: str,
    resume_entry: ResumeEntry,
    profile: UserProfile,
) -> OptimizeResult:
    """Synchronous Writer → Critic pipeline (D16)."""
    settings = get_settings()
    if settings.optimize_use_mock:
        return _mock_optimize(resume_entry, title, company)

    w_sys, w_user = build_writer_prompts(
        title=title, company=company,
        job_description=job_description,
        resume_content=resume_entry.content,
        verified_skills=profile.verified_skills,
        never_claim=profile.never_claim,
    )
    optimized = _writer_call(w_sys, w_user)

    c_sys, c_user = build_critic_prompts(
        original=resume_entry.content,
        optimized=optimized,
        verified_skills=profile.verified_skills,
        never_claim=profile.never_claim,
    )
    critic = _critic_call(c_sys, c_user)

    return OptimizeResult(
        resume_id=resume_entry.id,
        original=resume_entry.content,
        optimized=optimized,
        critic_approved=critic.approved,
        critic_notes=critic.notes,
        violations=critic.violations,
    )


def optimize_resume_stream(
    title: str,
    company: str,
    job_description: str,
    resume_entry: ResumeEntry,
    profile: UserProfile,
) -> Generator[str, None, None]:
    """SSE streaming Writer → Critic pipeline (D17).

    Yields SSE strings. Event shape: {"type": ..., ...}
    Types: status | token | done
    """
    settings = get_settings()

    if settings.optimize_use_mock:
        result = _mock_optimize(resume_entry, title, company)
        yield _sse({"type": "status", "stage": "writer", "resume_id": resume_entry.id})
        # Simulate token-by-token for mock
        for word in result.optimized.split(" "):
            yield _sse({"type": "token", "text": word + " "})
        yield _sse({"type": "status", "stage": "critic"})
        yield _sse({
            "type": "done",
            "resume_id": result.resume_id,
            "original": result.original,
            "optimized": result.optimized,
            "critic_approved": result.critic_approved,
            "critic_notes": result.critic_notes,
            "violations": result.violations,
        })
        return

    # ── Real LLM ──────────────────────────────────────────────────────────────
    yield _sse({"type": "status", "stage": "writer", "resume_id": resume_entry.id})

    w_sys, w_user = build_writer_prompts(
        title=title, company=company,
        job_description=job_description,
        resume_content=resume_entry.content,
        verified_skills=profile.verified_skills,
        never_claim=profile.never_claim,
    )

    optimized_parts: list[str] = []
    try:
        if settings.gemini_api_key:
            stream_fn = _stream_gemini_text
        elif settings.openai_api_key:
            stream_fn = _stream_openai_text
        else:
            raise RuntimeError("No LLM API key configured")

        for token in stream_fn(w_sys, w_user):
            optimized_parts.append(token)
            yield _sse({"type": "token", "text": token})
    except Exception as exc:
        logger.exception("Writer streaming failed")
        yield _sse({"type": "error", "message": str(exc)})
        return

    optimized = "".join(optimized_parts)

    yield _sse({"type": "status", "stage": "critic"})

    c_sys, c_user = build_critic_prompts(
        original=resume_entry.content,
        optimized=optimized,
        verified_skills=profile.verified_skills,
        never_claim=profile.never_claim,
    )
    critic = _critic_call(c_sys, c_user)

    yield _sse({
        "type": "done",
        "resume_id": resume_entry.id,
        "original": resume_entry.content,
        "optimized": optimized,
        "critic_approved": critic.approved,
        "critic_notes": critic.notes,
        "violations": critic.violations,
    })
