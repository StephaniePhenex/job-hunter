/** Full-page loading skeleton shown while the LLM analysis is in progress. */
export default function LoadingVibe() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-dash-bg text-dash-muted gap-6 p-8 bg-[radial-gradient(ellipse_120%_80%_at_50%_-20%,rgba(91,159,212,0.12),transparent)]">
      <div className="flex gap-2">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="block w-3 h-3 rounded-full bg-dash-accent animate-bounce"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
      <p className="text-sm tracking-widest uppercase text-dash-text">Analyzing match…</p>
      <div className="w-full max-w-layout px-4 space-y-4 mt-4">
        {[80, 60, 72].map((w, i) => (
          <div
            key={i}
            className="h-4 rounded-md bg-slate-200 animate-pulse mx-auto"
            style={{ width: `${w}%` }}
          />
        ))}
      </div>
    </div>
  );
}
