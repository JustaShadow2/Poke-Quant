"use client";

import type { RiskResponse } from "@/lib/api";

const LEVEL_COLORS: Record<string, string> = {
  low: "text-green-400",
  moderate: "text-yellow-400",
  high: "text-orange-400",
  very_high: "text-red-400",
};

const LEVEL_BAR_COLORS: Record<string, string> = {
  low: "bg-green-500",
  moderate: "bg-yellow-500",
  high: "bg-orange-500",
  very_high: "bg-red-500",
};

const LEVEL_LABELS: Record<string, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  very_high: "Very High",
};

export function RiskPanel({ risk }: { risk: RiskResponse }) {
  if (!risk.available) {
    return (
      <div className="panel px-4 py-3 text-sm text-terminal-muted">
        No risk assessment available yet. Run{" "}
        <code className="text-slate-300">pokequant phase2</code> to generate.
      </div>
    );
  }

  const overallColor = LEVEL_COLORS[risk.overall_level ?? "moderate"] ?? "text-slate-400";
  const overallLabel = LEVEL_LABELS[risk.overall_level ?? "moderate"] ?? "Unknown";

  return (
    <div className="panel px-4 py-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium uppercase tracking-wide text-terminal-muted">
          Risk Assessment
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-semibold ${overallColor}`}>
            {overallLabel}
          </span>
          <span className="tnum text-xs text-terminal-muted">
            {risk.overall_score?.toFixed(0)}/100
          </span>
        </div>
      </div>

      {/* Risk meter bar */}
      <div className="h-2 w-full rounded-full bg-terminal-border overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            LEVEL_BAR_COLORS[risk.overall_level ?? "moderate"] ?? "bg-slate-500"
          }`}
          style={{ width: `${Math.min(100, risk.overall_score ?? 0)}%` }}
        />
      </div>

      {/* Factor list */}
      {risk.factors && risk.factors.length > 0 && (
        <div className="space-y-2">
          {risk.factors.map((f) => {
            const factorColor = LEVEL_COLORS[f.level] ?? "text-slate-400";
            return (
              <div key={f.name} className="space-y-0.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 capitalize">
                    {f.name.replace(/_/g, " ")}
                  </span>
                  <span className={`font-medium ${factorColor}`}>
                    {LEVEL_LABELS[f.level] ?? f.level}
                  </span>
                </div>
                <div className="h-1 w-full rounded-full bg-terminal-border overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      LEVEL_BAR_COLORS[f.level] ?? "bg-slate-500"
                    }`}
                    style={{ width: `${Math.min(100, f.score * 20)}%` }}
                  />
                </div>
                <p className="text-[11px] text-terminal-muted leading-tight">
                  {f.narrative}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {risk.narrative && (
        <p className="text-xs text-terminal-muted border-t border-terminal-border pt-2">
          {risk.narrative}
        </p>
      )}
    </div>
  );
}
