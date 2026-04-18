import type { Decision, Confidence } from "../api";

interface Props {
  score: number;
  decision: Decision;
  confidence: Confidence;
  title: string;
  company: string;
}

const BADGE: Record<Decision, { label: string; cls: string }> = {
  APPLY:   { label: "Strong Fit",      cls: "bg-emerald-100 text-emerald-800 border border-emerald-200" },
  STRETCH: { label: "High Potential",  cls: "bg-amber-100 text-amber-900 border border-amber-200" },
  SKIP:    { label: "Low Fit",         cls: "bg-red-100 text-red-800 border border-red-200" },
};

const CONFIDENCE_CLS: Record<Confidence, string> = {
  HIGH:   "text-emerald-700",
  MEDIUM: "text-amber-700",
  LOW:    "text-red-700",
};

const SCORE_RING: Record<Decision, string> = {
  APPLY:   "stroke-emerald-500",
  STRETCH: "stroke-amber-500",
  SKIP:    "stroke-red-500",
};

export default function DecisionBar({ score, decision, confidence, title, company }: Props) {
  const badge = BADGE[decision];
  const r = 30;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;

  return (
    <div className="flex items-center gap-5 p-5 md:p-6 rounded-dash bg-dash-surface border border-[rgba(26,35,50,0.12)] shadow-[0_4px_24px_rgba(26,35,50,0.08)]">
      {/* Score ring */}
      <div className="relative flex-shrink-0">
        <svg width="80" height="80" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r={r} fill="none" stroke="#e2e8f0" strokeWidth="7" />
          <circle
            cx="40" cy="40" r={r}
            fill="none"
            className={SCORE_RING[decision]}
            strokeWidth="7"
            strokeDasharray={`${dash} ${circ}`}
            strokeLinecap="round"
            transform="rotate(-90 40 40)"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-xl font-bold text-dash-text">
          {score}
        </span>
      </div>

      {/* Labels */}
      <div className="flex-1 min-w-0">
        <h1 className="text-lg md:text-xl font-semibold text-dash-text truncate">{title}</h1>
        <p className="text-sm text-dash-muted truncate">{company}</p>
        <div className="flex flex-wrap items-center gap-3 mt-2">
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${badge.cls}`}>
            {badge.label}
          </span>
          <span className={`text-xs font-medium ${CONFIDENCE_CLS[confidence]}`}>
            {confidence} confidence
          </span>
        </div>
      </div>
    </div>
  );
}
