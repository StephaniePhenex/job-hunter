interface Props {
  strengths: string[];
  gaps: string[];
}

export default function StrengthsGaps({ strengths, gaps }: Props) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Strengths */}
      <div className="rounded-dash bg-dash-surface border border-[rgba(26,35,50,0.12)] shadow-[0_4px_24px_rgba(26,35,50,0.08)] p-4 md:p-5">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-emerald-700 mb-3">
          Strengths
        </h3>
        <ul className="space-y-2">
          {strengths.map((s, i) => (
            <li key={i} className="flex gap-2 text-sm text-dash-text">
              <span className="mt-0.5 text-emerald-600">✦</span>
              <span>{s}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Gaps */}
      <div className="rounded-dash bg-dash-surface border border-[rgba(26,35,50,0.12)] shadow-[0_4px_24px_rgba(26,35,50,0.08)] p-4 md:p-5">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-amber-800 mb-3">
          Gaps
        </h3>
        {gaps.length === 0 ? (
          <p className="text-sm text-dash-muted">No significant gaps identified.</p>
        ) : (
          <ul className="space-y-2">
            {gaps.map((g, i) => (
              <li key={i} className="flex gap-2 text-sm text-dash-text">
                <span className="mt-0.5 text-amber-600">△</span>
                <span>{g}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
