/**
 * Analysis SPA entry point.
 * URL pattern: /job/{jobId}/analysis  (served by FastAPI)
 *
 * Flow:
 *   1. Parse jobId from pathname.
 *   2. Fetch job details (GET /jobs/{id}).
 *   3. Auto-trigger deep analysis (POST /api/analyze).
 *   4. Render: DecisionBar · Radar · StrengthsGaps · ResumeCard.
 */
import { useQuery } from "@tanstack/react-query";
import { fetchJob, postAnalyze } from "./api";
import LoadingVibe from "./components/LoadingVibe";
import DecisionBar from "./components/DecisionBar";
import RadarChart from "./components/RadarChart";
import StrengthsGaps from "./components/StrengthsGaps";
import ResumeCard from "./components/ResumeCard";
import OptimizePanel from "./components/OptimizePanel";

function parseJobId(): number | null {
  const m = window.location.pathname.match(/\/job\/(\d+)/);
  return m ? parseInt(m[1], 10) : null;
}

export default function App() {
  const jobId = parseJobId();

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId!),
    enabled: jobId !== null,
  });

  const analyzeQuery = useQuery({
    queryKey: ["analyze", jobId],
    queryFn: () => postAnalyze(jobId!),
    enabled: jobId !== null && jobQuery.isSuccess,
    staleTime: Infinity,  // don't re-run on refocus; use force_refresh if needed
  });

  // ─── Error states ─────────────────────────────────────────────────────────

  if (jobId === null) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-dash-bg text-red-600 p-8">
        <p>No job ID in URL. Expected <code className="bg-white px-1 rounded border border-dash-border">/job/&lt;id&gt;/analysis</code>.</p>
      </div>
    );
  }

  if (jobQuery.isError) {
    return (
      <ErrorScreen message={`Failed to load job: ${(jobQuery.error as Error).message}`} />
    );
  }

  if (analyzeQuery.isError) {
    return (
      <ErrorScreen message={`Analysis failed: ${(analyzeQuery.error as Error).message}`} />
    );
  }

  // ─── Loading ───────────────────────────────────────────────────────────────

  if (jobQuery.isLoading || analyzeQuery.isLoading || !analyzeQuery.data) {
    return <LoadingVibe />;
  }

  const job = jobQuery.data!;
  const result = analyzeQuery.data!;

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-dash-bg text-dash-text bg-[radial-gradient(ellipse_120%_80%_at_50%_-20%,rgba(91,159,212,0.12),transparent)]">
      <div className="max-w-layout w-full mx-auto px-5 py-8 md:px-6 space-y-5">

        {/* Match dashboard: full-width header strip */}
        <header className="flex flex-wrap items-end justify-between gap-4 print:hidden">
          <div>
            <h1 className="text-2xl font-semibold text-dash-text tracking-tight m-0">
              Job match analysis
            </h1>
            <p className="text-sm text-dash-muted mt-1 m-0">
              Fit scores, narrative, and resume routing for this posting
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href="/"
              className="text-sm text-dash-muted hover:text-dash-accent border border-[rgba(26,35,50,0.12)] bg-white rounded-lg px-3 py-2 transition-colors"
            >
              ← Back to list
            </a>
            <button
              type="button"
              onClick={() => window.print()}
              className="text-sm font-semibold text-[#0a0e14] bg-dash-accent hover:opacity-90 rounded-lg px-3 py-2 border-0 cursor-pointer transition-opacity"
              title="Export analysis as PDF via browser print dialog"
            >
              Export PDF
            </button>
          </div>
        </header>

        {/* D6: Decision bar */}
        <DecisionBar
          score={result.score}
          decision={result.decision}
          confidence={result.confidence}
          title={job.title}
          company={job.company}
        />

        {/* D7: Radar + Strengths/Gaps */}
        <div className="rounded-dash bg-dash-surface border border-[rgba(26,35,50,0.12)] shadow-[0_4px_24px_rgba(26,35,50,0.08)] p-5 md:p-6">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-dash-muted mb-4">
            Match Dimensions
          </h2>
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center gap-8">
            <RadarChart
              hardSkills={result.dimensions.hard_skills}
              experience={result.dimensions.experience}
              synergy={result.dimensions.synergy}
            />
            <div className="flex-1 space-y-3 text-sm w-full min-w-0">
              {(
                [
                  ["Skills",     result.dimensions.hard_skills],
                  ["Experience", result.dimensions.experience],
                  ["Leverage",   result.dimensions.synergy],
                ] as [string, number][]
              ).map(([label, val]) => (
                <div key={label}>
                  <div className="flex justify-between text-dash-muted mb-0.5">
                    <span>{label}</span>
                    <span className="font-medium text-dash-text">{val}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-dash-accent transition-all"
                      style={{ width: `${val}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <StrengthsGaps strengths={result.strengths} gaps={result.gaps} />

        {/* D8: Resume card + strategy */}
        <ResumeCard
          recommendedResumeId={result.recommended_resume_id}
          recommendedResumeReason={result.recommended_resume_reason}
          strategy={result.strategy}
          decision={result.decision}
        />

        {/* D18: Optimize dual-pane panel */}
        <OptimizePanel
          jobId={jobId!}
          jobDescription={job.description}
          resumeId={result.recommended_resume_id}
        />

        {/* Guard debug info (only when guard fired) */}
        {result.guard_adjusted && (
          <details className="text-xs text-dash-muted rounded-dash bg-dash-surface border border-[rgba(26,35,50,0.12)] px-4 py-3">
            <summary className="cursor-pointer hover:text-dash-text">Guard adjustments</summary>
            <ul className="mt-2 space-y-0.5 pl-3 text-dash-text">
              {result.guard_notes.map((n, i) => <li key={i}>{n}</li>)}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}

function ErrorScreen({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-dash-bg text-red-600 gap-4 p-8">
      <p className="text-center max-w-lg">{message}</p>
      <a href="/" className="text-sm text-dash-accent font-medium hover:underline">← Back to list</a>
    </div>
  );
}
