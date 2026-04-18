#!/usr/bin/env npx ts-node
/**
 * scripts/test-analyze.ts
 *
 * Prompt iteration tool for the Analyze agent.
 * Calls the real LLM with a sample JD and prints the structured result.
 *
 * Usage:
 *   npx ts-node scripts/test-analyze.ts
 *
 * Prerequisites:
 *   npm install -g ts-node typescript
 *   Set GEMINI_API_KEY or OPENAI_API_KEY in your environment (or .env).
 *
 * Edit SAMPLE_JD and SAMPLE_PROFILE below to iterate on prompts.
 */

import * as fs from "fs";
import * as path from "path";

// ─── Load .env (optional) ────────────────────────────────────────────────────
const envPath = path.resolve(__dirname, "../.env");
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const m = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
    if (m) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
}

// ─── Sample inputs (edit to iterate) ─────────────────────────────────────────

const SAMPLE_JD = `
Software Engineer Intern — Acme AI Labs (Toronto, ON)

We are building next-generation AI-powered productivity tools for teams.
You will work on our full-stack platform: React frontend, FastAPI backend, and
LLM integration pipelines.

Requirements:
- Python (FastAPI, Pydantic) + TypeScript/React
- Experience with REST APIs and basic SQL
- Bonus: LLM / prompt engineering, Docker

Compensation: $25–35/hr CAD. Remote-friendly. Fall 2026 term.
`.trim();

const SAMPLE_PROFILE = {
  location_focus: "Canada",
  term: "Fall 2026 internship",
  interests: [
    "Full-stack AI, LLM, and SaaS applications",
    "Product-minded engineering",
    "Media and content technology",
  ],
};

// No resumes yet (Phase 2 adds them from user_profile.yaml).
const SAMPLE_RESUMES: Array<{ id: string; content: string }> = [];

// ─── Prompt assembly (mirrors app/agents/analyze_prompt.py) ──────────────────

const SYSTEM_PROMPT = `\
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
  "strategy": {"focus": "string", "key_message": "string", "risk": "string"}
}`;

function buildUserPrompt(jd: string, profile: object, resumes: object[]): string {
  return [
    `# Job: Software Engineer Intern @ Acme AI Labs\n`,
    `## Job Description\n${jd}\n`,
    `## User Core Profile\n${JSON.stringify(profile, null, 2)}\n`,
    `## Resumes\n${JSON.stringify(resumes, null, 2)}`,
  ].join("\n");
}

// ─── LLM call ─────────────────────────────────────────────────────────────────

async function callGemini(system: string, user: string): Promise<string> {
  const { GoogleGenerativeAI } = await import("@google/generative-ai");
  const client = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
  const model = client.getGenerativeModel({
    model: process.env.GEMINI_MODEL ?? "gemini-2.0-flash",
    systemInstruction: system,
    generationConfig: { temperature: 0.2, responseMimeType: "application/json" },
  });
  const result = await model.generateContent(user);
  return result.response.text();
}

async function callOpenAI(system: string, user: string): Promise<string> {
  const OpenAI = (await import("openai")).default;
  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const resp = await client.chat.completions.create({
    model: process.env.OPENAI_MODEL ?? "gpt-4o-mini",
    messages: [
      { role: "system", content: system },
      { role: "user", content: user },
    ],
    response_format: { type: "json_object" },
    temperature: 0.2,
  });
  return resp.choices[0].message.content ?? "{}";
}

// ─── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const userPrompt = buildUserPrompt(SAMPLE_JD, SAMPLE_PROFILE, SAMPLE_RESUMES);

  console.log("─── System prompt ──────────────────────────────────────────");
  console.log(SYSTEM_PROMPT);
  console.log("\n─── User prompt ────────────────────────────────────────────");
  console.log(userPrompt);
  console.log("\n─── Calling LLM... ─────────────────────────────────────────\n");

  let rawText: string;
  if (process.env.GEMINI_API_KEY) {
    console.log("Provider: Gemini");
    rawText = await callGemini(SYSTEM_PROMPT, userPrompt);
  } else if (process.env.OPENAI_API_KEY) {
    console.log("Provider: OpenAI");
    rawText = await callOpenAI(SYSTEM_PROMPT, userPrompt);
  } else {
    console.error("ERROR: Set GEMINI_API_KEY or OPENAI_API_KEY in environment or .env");
    process.exit(1);
  }

  console.log("\n─── Raw LLM output ─────────────────────────────────────────");
  console.log(rawText);

  try {
    const parsed = JSON.parse(rawText);
    console.log("\n─── Parsed result ──────────────────────────────────────────");
    console.log(JSON.stringify(parsed, null, 2));
    console.log("\n✓ Valid JSON");
  } catch (e) {
    console.error("\n✗ JSON parse failed:", e);
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
