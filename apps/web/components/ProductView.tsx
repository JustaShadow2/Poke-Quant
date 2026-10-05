"use client";

import { useMemo, useState } from "react";

import {
  ConfidenceBadge,
  DataCoverageBadge,
  SourceBadge,
  confidenceFromBand,
} from "@/components/badges";
import { ForecastChart, type ObservedPoint } from "@/components/ForecastChart";
import {
  HORIZONS,
  HORIZON_DAYS,
  type ForecastResponse,
  type Horizon,
  bandFromQuantiles,
} from "@/lib/api";
import { addDaysISO, deltaClass, formatPct, formatUSD } from "@/lib/format";

const HORIZON_LABEL: Record<Horizon, string> = {
  d30: "30d",
  d90: "90d",
  d180: "180d",
  d365: "365d",
};

function Kpi({
  label,
  value,
  sub,
  valueClass = "text-white",
}: {
  label: string;
  value: string;
  sub?: string;
  valueClass?: string;
}) {
  return (
    <div className="panel px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-terminal-muted">
        {label}
      </div>
      <div className={`tnum mt-1 text-xl font-semibold ${valueClass}`}>{value}</div>
      {sub ? <div className="tnum mt-0.5 text-xs text-terminal-muted">{sub}</div> : null}
    </div>
  );
}

export function ProductView({
  observed,
  forecasts,
}: {
  observed: ObservedPoint[];
  forecasts: Record<Horizon, ForecastResponse | null>;
}) {
  const available = HORIZONS.filter((h) => forecasts[h] !== null);
  const initial: Horizon = forecasts.d90 ? "d90" : (available[0] ?? "d90");
  const [horizon, setHorizon] = useState<Horizon>(initial);

  const forecast = forecasts[horizon];
  const band = forecast ? bandFromQuantiles(forecast.quantiles_price) : null;

  const chartForecast = useMemo(() => {
    if (!forecast) return null;
    const b = band ?? {
      low: forecast.predicted_price,
      median: forecast.predicted_price,
      high: forecast.predicted_price,
    };
    return {
      asOf: forecast.as_of,
      horizonTime: addDaysISO(forecast.as_of, HORIZON_DAYS[horizon]),
      last: forecast.last_price,
      low: b.low,
      median: b.median,
      high: b.high,
    };
  }, [forecast, band, horizon]);

  const lastPrice =
    forecast?.last_price ?? observed[observed.length - 1]?.value ?? null;
  const prev = observed[observed.length - 2]?.value ?? null;
  const dayChange =
    lastPrice !== null && prev !== null && prev !== 0
      ? (lastPrice / prev - 1) * 100
      : null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi
          label="Market"
          value={formatUSD(lastPrice)}
          sub={dayChange !== null ? `${formatPct(dayChange)} last obs` : undefined}
          valueClass="text-white"
        />
        <Kpi
          label={`Forecast ${HORIZON_LABEL[horizon]}`}
          value={forecast ? formatPct(forecast.expected_change_pct) : "—"}
          sub={forecast ? `to ${formatUSD(forecast.predicted_price)}` : "no model"}
          valueClass={deltaClass(forecast?.expected_change_pct)}
        />
        <Kpi
          label="90% interval"
          value={band ? `${formatUSD(band.low)} – ${formatUSD(band.high)}` : "—"}
          sub={forecast ? `at ${HORIZON_LABEL[horizon]} horizon` : undefined}
        />
        <Kpi
          label="Model"
          value={forecast?.model_version ? `v${forecast.model_version}` : "—"}
          sub={forecast?.source ? `${forecast.source} · ${forecast.horizon}` : undefined}
        />
      </div>

      <div className="panel">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-terminal-border px-4 py-2">
          <div className="text-sm font-medium text-slate-200">Price &amp; Forecast</div>
          <div className="flex items-center gap-1">
            {HORIZONS.map((h) => {
              const enabled = forecasts[h] !== null;
              const active = h === horizon;
              return (
                <button
                  key={h}
                  type="button"
                  disabled={!enabled}
                  onClick={() => setHorizon(h)}
                  className={[
                    "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                    active
                      ? "bg-info/20 text-info"
                      : enabled
                        ? "text-terminal-muted hover:bg-white/5 hover:text-white"
                        : "cursor-not-allowed text-terminal-border",
                  ].join(" ")}
                >
                  {HORIZON_LABEL[h]}
                </button>
              );
            })}
          </div>
        </div>
        <div className="px-2 py-3">
          <ForecastChart observed={observed} forecast={chartForecast} />
        </div>
      </div>

      {forecast ? (
        <div className="flex flex-wrap items-center gap-2">
          {band ? (
            <ConfidenceBadge
              level={confidenceFromBand(forecast.last_price, band.low, band.high)}
            />
          ) : null}
          <SourceBadge source={forecast.source} />
          <DataCoverageBadge synthetic={forecast.is_synthetic} />
          {forecast.disclaimer ? (
            <span className="text-xs text-terminal-muted">{forecast.disclaimer}</span>
          ) : null}
        </div>
      ) : (
        <div className="panel px-4 py-3 text-sm text-terminal-muted">
          No forecast available yet. Train a model:{" "}
          <code className="text-slate-300">pokequant train && pokequant forecast run</code>
          .
        </div>
      )}
    </div>
  );
}
