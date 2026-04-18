"""Prompt assembly for the Analyze agent.

Builds (system_prompt, user_prompt) from job description, user profile, and resumes.
"""

from __future__ import annotations

import json

from app.agents.profile import UserProfile

_SYSTEM_PROMPT = """\
你是一位拥有 20 年经验的技术猎头和工程总监，擅长挖掘候选人的跨学科潜力（PhD/Academic + CS Engineering）。

# Task
基于提供的岗位详情(JD)、用户核心背景和简历库，进行深度匹配分析并给出投递决策。

# Constraints
1. 真实性原则：禁止虚构任何用户未提及的技能或经历。
2. 简历路由：必须从提供的 Resumes 列表中选择最合适的一个；若列表为空则 recommended_resume_id 输出空字符串。
3. 输出格式：严禁任何解释性文字、Markdown 代码围栏或前后缀，只输出符合 Schema 的标准 JSON。
4. 叙事感（Strengths）：strengths 每条用完整、可读句子；避免干瘪关键词堆叠；须遵守真实性原则。
5. 评估维度：
   - Hard Skill Match：技术栈与 JD 对齐度。
   - Experience Match：职业阶段与职级匹配度。
   - Synergy Match：PhD/研究/传播等对岗位的增量价值。
6. 置信度：输出 confidence（HIGH | MEDIUM | LOW），反映证据充分性与匹配确定性。

# Output JSON Schema
{
  "score": number,
  "dimensions": {"hard_skills": number, "experience": number, "synergy": number},
  "decision": "APPLY" | "SKIP" | "STRETCH",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "strengths": [string],
  "gaps": [string],
  "recommended_resume_id": "string",
  "recommended_resume_reason": "string (optional, one sentence why this resume fits best)",
  "strategy": {"focus": "string", "key_message": "string", "risk": "string"}
}"""


def build_prompts(
    job_description: str,
    title: str,
    company: str,
    user_profile: UserProfile,
    resumes: list[dict],
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the analyze LLM call."""
    profile_json = user_profile.model_dump_json(indent=2)
    resumes_json = json.dumps(resumes, ensure_ascii=False, indent=2)

    user_prompt = (
        f"# Job: {title} @ {company}\n\n"
        f"## Job Description\n{job_description}\n\n"
        f"## User Core Profile\n{profile_json}\n\n"
        f"## Resumes\n{resumes_json}"
    )
    return _SYSTEM_PROMPT, user_prompt
