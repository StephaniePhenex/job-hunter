import type { AnalyzeStrategy, Decision } from "../api";

interface Props {
  recommendedResumeId: string;
  recommendedResumeReason?: string;
  strategy: AnalyzeStrategy;
  decision: Decision;
}

const STRETCH_TOOLTIP =
  "High Potential: you meet some requirements but may need to frame your background carefully. Worth applying if you can tailor the narrative.";

export default function ResumeCard({ recommendedResumeId, recommendedResumeReason, strategy, decision }: Props) {
  return (
    <div className="space-y-4">
      {/* Strategy card */}
      <div className="rounded-dash bg-dash-surface border border-[rgba(26,35,50,0.12)] shadow-[0_4px_24px_rgba(26,35,50,0.08)] p-4 md:p-5 space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-dash-accent">
          Strategy
        </h3>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium bg-sky-100 text-sky-900 border border-sky-200 rounded px-2 py-0.5">
            {strategy.focus}
          </span>
          {decision === "STRETCH" && (
            <span
              className="text-xs text-amber-800 cursor-help border-b border-dotted border-amber-600"
              title={STRETCH_TOOLTIP}
            >
              High Potential — what does this mean?
            </span>
          )}
        </div>

        <p className="text-sm text-dash-text leading-relaxed">{strategy.key_message}</p>

        {strategy.risk && (
          <p className="text-xs text-dash-muted italic">
            <span className="text-amber-700 not-italic font-medium">Risk: </span>
            {strategy.risk}
          </p>
        )}
      </div>

      {/* Recommended resume */}
      {recommendedResumeId && (
        <div className="rounded-dash bg-dash-surface border border-[rgba(26,35,50,0.12)] shadow-[0_4px_24px_rgba(26,35,50,0.08)] p-4 md:p-5">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-dash-accent mb-2">
            Recommended Resume
          </h3>
          <p className="text-sm text-dash-text font-mono break-all">{recommendedResumeId}</p>
          {recommendedResumeReason && (
            <p className="text-xs text-dash-muted mt-1">{recommendedResumeReason}</p>
          )}
        </div>
      )}

    </div>
  );
}
