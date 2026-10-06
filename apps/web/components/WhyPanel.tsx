"use client";

import type { ExplanationResponse } from "@/lib/api";

const FEATURE_LABELS: Record<string, string> = {
  ret_7: "7-day return",
  ret_30: "30-day return",
  ret_90: "90-day return",
  mom_accel: "momentum accel.",
  sma_ratio_20: "price vs SMA20",
  sma_ratio_50: "price vs SMA50",
  ema_ratio_20: "price vs EMA20",
  rsi_14: "RSI (14d)",
  macd_hist: "MACD momentum",
  bb_pctb_20: "Bollinger %B",
  bb_width_20: "volatility (BB width)",
  vol_30: "30d volatility",
  vol_90: "90d volatility",
  max_dd_180: "max drawdown",
  log_price: "price level",
  log_active_listings: "listing count",
  listings_chg_30: "listings trend",
  log_volume_30: "volume (30d)",
  attention_index: "attention",
  attention_chg_30: "attention trend",
  days_since_release: "days since release",
  months_since_release: "maturity",
  month_sin: "seasonal",
  month_cos: "seasonal",
  is_q4: "Q4 season",
};

function label(feature: string): string {
  return FEATURE_LABELS[feature] ?? feature.replace(/_/g, " ");
}

export function WhyPanel({ explanation }: { explanation: ExplanationResponse }) {
  if (!explanation.available) {
    return (
      <div className="panel px-4 py-3 text-sm text-terminal-muted">
        No explanation available yet. Run{" "}
        <code className="text-slate-300">pokequant phase2</code> to generate.
      </div>
    );
  }

  return (
    <div className="panel px-4 py-3 space-y-3">
      <div className="text-xs font-medium uppercase tracking-wide text-terminal-muted">
        Why this forecast
      </div>

      {explanation.narrative && (
        <p className="text-sm text-slate-300 leading-relaxed">
          {explanation.narrative}
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Positive drivers */}
        {explanation.top_positive && explanation.top_positive.length > 0 && (
          <div>
            <div className="mb-1 text-xs font-medium text-green-400">
              Pushing up
            </div>
            <div className="space-y-1">
              {explanation.top_positive.map((a) => (
                <div
                  key={a.feature}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-slate-300">{label(a.feature)}</span>
                  <span className="tnum text-green-400">
                    +{(a.shap_value * 100).toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Negative drivers */}
        {explanation.top_negative && explanation.top_negative.length > 0 && (
          <div>
            <div className="mb-1 text-xs font-medium text-red-400">
              Pulling down
            </div>
            <div className="space-y-1">
              {explanation.top_negative.map((a) => (
                <div
                  key={a.feature}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-slate-300">{label(a.feature)}</span>
                  <span className="tnum text-red-400">
                    {(a.shap_value * 100).toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
