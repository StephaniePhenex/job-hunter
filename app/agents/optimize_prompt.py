"""Prompt builders for the Optimize agent (Writer + Critic)."""

from __future__ import annotations


_WRITER_SYSTEM = """\
你是一位专业的简历优化师，擅长将候选人简历针对特定岗位进行精准调整。

# 核心约束（违反即失败）
1. **真实性铁律**：只能使用 [已验证技能] 中列出的技能；绝对禁止添加 [禁止声称] 列表中的任何内容。
2. **不虚构经历**：不得编造项目、职位或成就；只能重新表述已有内容。
3. **输出格式**：直接输出优化后的简历纯文本，不加任何解释、前缀或 Markdown 代码围栏。
4. **语言**：保持与原始简历相同的语言（中/英）。"""

_WRITER_USER_TMPL = """\
# 目标岗位
{title} @ {company}

## 岗位描述
{job_description}

## 原始简历
{resume_content}

## 已验证技能（可强调，但不得凭空添加未列出的）
{verified_skills}

## 禁止声称（绝对不得出现在输出中）
{never_claim}

请输出针对该岗位优化后的简历："""

_CRITIC_SYSTEM = """\
你是一位严格的简历合规审核员。你的唯一职责是检查优化后的简历是否违反了反虚构约束。

输出严格遵守以下 JSON Schema，不加任何解释：
{
  "approved": boolean,
  "notes": "string（总体评语，一两句话）",
  "violations": ["string（每条具体违规描述）"]
}"""

_CRITIC_USER_TMPL = """\
# 原始简历
{original}

# 优化后简历
{optimized}

# 禁止声称列表（优化后简历中不得出现）
{never_claim}

# 已验证技能（优化后简历只能声称这些技能）
{verified_skills}

请检查优化后简历是否违反约束，输出审核 JSON："""


def build_writer_prompts(
    title: str,
    company: str,
    job_description: str,
    resume_content: str,
    verified_skills: list[str],
    never_claim: list[str],
) -> tuple[str, str]:
    user = _WRITER_USER_TMPL.format(
        title=title,
        company=company,
        job_description=job_description[:8000],
        resume_content=resume_content,
        verified_skills="\n".join(f"- {s}" for s in verified_skills) or "（未配置）",
        never_claim="\n".join(f"- {s}" for s in never_claim) or "（未配置）",
    )
    return _WRITER_SYSTEM, user


def build_critic_prompts(
    original: str,
    optimized: str,
    verified_skills: list[str],
    never_claim: list[str],
) -> tuple[str, str]:
    user = _CRITIC_USER_TMPL.format(
        original=original,
        optimized=optimized,
        never_claim="\n".join(f"- {s}" for s in never_claim) or "（未配置）",
        verified_skills="\n".join(f"- {s}" for s in verified_skills) or "（未配置）",
    )
    return _CRITIC_SYSTEM, user
