"use client";

import type { ScoreResponse } from "@/lib/api";

const BAND_COLORS: Record<string, string> = {
  "A+": "bg-green-500/20 text-green-400 border-green-500/40",
  A: "bg-green-500/15 text-green-400 border-green-500/30",
  B: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  C: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  D: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  F: "bg-red-500/15 text-red-400 border-red-500/30",
};

export function ScoreBadge({ score }: { score: ScoreResponse }) {
  if (!score.available || score.score === undefined || score.band === undefined) {
    return (
      <div className="panel px-4 py-3">
        <div className="text-xs uppercase tracking-wide text-terminal-muted">
          PQ Score
        </div>
        <div className="mt-1 text-sm text-terminal-muted">Not available</div>
      </div>
    );
  }

  const bandClass = BAND_COLORS[score.band] ?? "bg-slate-500/15 text-slate-400 border-slate-500/30";

  return (
    <div className="panel px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-terminal-muted">
        PQ Score
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="tnum text-2xl font-bold text-white">
          {Math.round(score.score)}
        </span>
        <span
          className={`rounded border px-2 py-0.5 text-xs font-semibold ${bandClass}`}
        >
          {score.band}
        </span>
      </div>
      <div className="mt-1 text-xs text-terminal-muted">
        {score.profile} profile
        {score.data_coverage !== undefined && score.data_coverage < 1
          ? ` · ${Math.round(score.data_coverage * 100)}% data coverage`
          : ""}
      </div>
    </div>
  );
}

export function ScoreBreakdown({ score }: { score: ScoreResponse }) {
  if (!score.available || !score.components) return null;

  return (
    <div className="panel px-4 py-3">
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-terminal-muted">
        Score Breakdown
      </div>
      <div className="space-y-1.5">
        {score.components.map((c) => (
          <div key={c.name} className="flex items-center gap-2 text-xs">
            <span className="w-28 truncate text-slate-300">
              {c.name.replace(/_/g, " ")}
            </span>
            <div className="h-1.5 flex-1 rounded-full bg-terminal-border overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  c.direction === "positive"
                    ? "bg-green-500"
                    : c.direction === "negative"
                      ? "bg-red-500"
                      : "bg-slate-500"
                }`}
                style={{ width: `${Math.min(100, c.percentile)}%` }}
              />
            </div>
            <span className="tnum w-10 text-right text-terminal-muted">
              {c.contribution.toFixed(1)}
            </span>
          </div>
        ))}
        {(score.reprint_penalty ?? 0) > 0 && (
          <div className="flex items-center gap-2 text-xs text-red-400">
            <span className="w-28">reprint risk</span>
            <span>−{score.reprint_penalty?.toFixed(1)}</span>
          </div>
        )}
        {(score.risk_penalty ?? 0) > 0 && (
          <div className="flex items-center gap-2 text-xs text-red-400">
            <span className="w-28">risk drag</span>
            <span>−{score.risk_penalty?.toFixed(1)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
