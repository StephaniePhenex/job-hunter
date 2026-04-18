/** Typed API wrappers for the FastAPI backend. */

export interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  url: string;
  description: string;
  source: string;
  match_score: number | null;
  priority: string | null;
  created_at: string | null;
}

export interface AnalyzeDimensions {
  hard_skills: number;
  experience: number;
  synergy: number;
}

export interface AnalyzeStrategy {
  focus: string;
  key_message: string;
  risk: string;
}

export type Decision = "APPLY" | "SKIP" | "STRETCH";
export type Confidence = "HIGH" | "MEDIUM" | "LOW";

export interface AnalyzeResult {
  score: number;
  dimensions: AnalyzeDimensions;
  decision: Decision;
  confidence: Confidence;
  strengths: string[];
  gaps: string[];
  recommended_resume_id: string;
  recommended_resume_reason: string;
  strategy: AnalyzeStrategy;
  guard_adjusted: boolean;
  guard_notes: string[];
}

export interface OptimizeDoneEvent {
  resume_id: string;
  original: string;
  optimized: string;
  critic_approved: boolean;
  critic_notes: string;
  violations: string[];
}

export type OptimizeSSEEvent =
  | { type: "status"; stage: "writer" | "critic"; resume_id?: string }
  | { type: "token"; text: string }
  | { type: "done" } & OptimizeDoneEvent
  | { type: "error"; message: string };

/** Stream POST /api/optimize/stream — calls onEvent for each SSE message. */
export async function streamOptimize(
  jobId: number,
  resumeId: string,
  onEvent: (evt: OptimizeSSEEvent) => void,
): Promise<void> {
  const resp = await fetch("/api/optimize/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, resume_id: resumeId }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail ?? `Optimize failed (${resp.status})`);
  }
  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          onEvent(JSON.parse(line.slice(6)) as OptimizeSSEEvent);
        } catch { /* skip malformed */ }
      }
    }
  }
}

export async function fetchJob(jobId: number): Promise<Job> {
  const resp = await fetch(`/jobs/${jobId}`);
  if (!resp.ok) throw new Error(`Job ${jobId} not found (${resp.status})`);
  return resp.json();
}

export async function postAnalyze(
  jobId: number,
  forceRefresh = false
): Promise<AnalyzeResult> {
  const resp = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, force_refresh: forceRefresh }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail ?? `Analyze failed (${resp.status})`);
  }
  return resp.json();
}
