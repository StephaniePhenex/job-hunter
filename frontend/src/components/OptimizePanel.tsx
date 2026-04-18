/**
 * D18 — Dual-pane Optimize UI.
 * Left: Job Description  |  Right: streaming optimized resume
 */
import { useState, useRef } from "react";
import { streamOptimize, type OptimizeDoneEvent } from "../api";

interface Props {
  jobId: number;
  jobDescription: string;
  resumeId: string;   // from analyze result
}

type Stage = "idle" | "writer" | "critic" | "done" | "error";

export default function OptimizePanel({ jobId, jobDescription, resumeId }: Props) {
  const [open, setOpen] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const [streamedText, setStreamedText] = useState("");
  const [result, setResult] = useState<OptimizeDoneEvent | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const rightRef = useRef<HTMLPreElement>(null);

  async function handleOptimize() {
    setStage("writer");
    setStreamedText("");
    setResult(null);
    setErrorMsg("");

    try {
      await streamOptimize(jobId, resumeId, (evt) => {
        if (evt.type === "status") {
          setStage(evt.stage);
        } else if (evt.type === "token") {
          setStreamedText((t) => {
            const next = t + evt.text;
            // Auto-scroll right pane
            requestAnimationFrame(() => {
              if (rightRef.current) rightRef.current.scrollTop = rightRef.current.scrollHeight;
            });
            return next;
          });
        } else if (evt.type === "done") {
          setResult(evt as unknown as OptimizeDoneEvent);
          setStreamedText(evt.optimized ?? "");
          setStage("done");
        } else if (evt.type === "error") {
          setErrorMsg(evt.message);
          setStage("error");
        }
      });
    } catch (e) {
      setErrorMsg((e as Error).message);
      setStage("error");
    }
  }

  const isRunning = stage === "writer" || stage === "critic";

  return (
    <div className="rounded-dash border border-[rgba(26,35,50,0.12)] shadow-[0_4px_24px_rgba(26,35,50,0.08)] overflow-hidden bg-dash-surface">
      {/* Header / toggle */}
      <button
        type="button"
        className="w-full flex items-center justify-between px-5 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-left border-b border-[rgba(26,35,50,0.08)]"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="text-sm font-semibold text-dash-accent">
          ✦ Optimize Resume for This Role
        </span>
        <span className="text-dash-muted text-xs">{open ? "▲ collapse" : "▼ expand"}</span>
      </button>

      {open && (
        <div className="bg-dash-surface">
          {/* Optimize button */}
          <div className="px-5 py-3 border-b border-[rgba(26,35,50,0.08)] flex flex-wrap items-center gap-4">
            <button
              type="button"
              disabled={isRunning}
              onClick={handleOptimize}
              className="px-4 py-2 rounded-lg bg-dash-accent hover:opacity-90 disabled:opacity-50 text-sm font-semibold text-[#0a0e14] transition-opacity border-0 cursor-pointer"
            >
              {isRunning ? (stage === "writer" ? "Writing…" : "Critic reviewing…") : "Optimize"}
            </button>
            {resumeId && (
              <span className="text-xs text-dash-muted">
                Resume: <span className="font-mono text-dash-text">{resumeId}</span>
              </span>
            )}
          </div>

          {/* Dual pane */}
          <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-[rgba(26,35,50,0.08)]" style={{ minHeight: "280px" }}>
            {/* Left — JD */}
            <div className="flex flex-col bg-white">
              <p className="text-xs font-semibold uppercase tracking-widest text-dash-muted px-4 pt-3 pb-1">
                Job Description
              </p>
              <pre className="flex-1 text-xs text-dash-muted leading-relaxed px-4 pb-4 overflow-auto whitespace-pre-wrap bg-slate-50/50" style={{ maxHeight: "360px" }}>
                {jobDescription || "No description available."}
              </pre>
            </div>

            {/* Right — Resume */}
            <div className="flex flex-col bg-white">
              <p className="text-xs font-semibold uppercase tracking-widest text-dash-muted px-4 pt-3 pb-1">
                {stage === "idle" ? "Original Resume" : stage === "done" ? "Optimized Resume" : "Optimizing…"}
              </p>
              <pre
                ref={rightRef}
                className="flex-1 text-xs text-dash-text leading-relaxed px-4 pb-4 overflow-auto whitespace-pre-wrap bg-slate-50/50"
                style={{ maxHeight: "360px" }}
              >
                {streamedText || (stage === "idle" ? "(click Optimize to start)" : "")}
                {isRunning && <span className="animate-pulse text-dash-accent">▌</span>}
              </pre>
            </div>
          </div>

          {/* Critic result */}
          {stage === "done" && result && (
            <div className={`px-5 py-3 border-t border-[rgba(26,35,50,0.08)] text-sm ${result.critic_approved ? "text-emerald-700 bg-emerald-50/50" : "text-amber-800 bg-amber-50/50"}`}>
              <span className="font-semibold">{result.critic_approved ? "✓ Critic approved" : "△ Critic flagged issues"}</span>
              {result.critic_notes && <span className="ml-2 text-dash-muted">{result.critic_notes}</span>}
              {result.violations.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-xs text-amber-800">
                  {result.violations.map((v, i) => <li key={i}>• {v}</li>)}
                </ul>
              )}
            </div>
          )}

          {/* Error */}
          {stage === "error" && (
            <div className="px-5 py-3 border-t border-[rgba(26,35,50,0.08)] text-sm text-red-700 bg-red-50">
              ✗ {errorMsg}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
