import Link from "next/link";
import { notFound } from "next/navigation";

import { DataCoverageBadge } from "@/components/badges";
import type { ObservedPoint } from "@/components/ForecastChart";
import { ProductView } from "@/components/ProductView";
import { RiskPanel } from "@/components/RiskPanel";
import { ScoreBadge, ScoreBreakdown } from "@/components/ScoreBadge";
import { WhyPanel } from "@/components/WhyPanel";
import {
  HORIZONS,
  type ForecastResponse,
  type Horizon,
  type ExplanationResponse,
  type ScoreResponse,
  type RiskResponse,
  getExplanation,
  getForecast,
  getInstrument,
  getPrices,
  getRisk,
  getScore,
} from "@/lib/api";
import { formatDate, formatUSD } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const [instrument, prices] = await Promise.all([getInstrument(id), getPrices(id)]);
  if (instrument === null) notFound();

  const [forecastList, scoreData, riskData, explanationData] = await Promise.all([
    Promise.all(HORIZONS.map((h) => getForecast(id, h))),
    getScore(id, "d90"),
    getRisk(id, "d90"),
    getExplanation(id, "d90"),
  ]);
  const forecasts = Object.fromEntries(
    HORIZONS.map((h, i) => [h, forecastList[i]]),
  ) as Record<Horizon, ForecastResponse | null>;

  const observed: ObservedPoint[] = (prices?.points ?? []).map((p) => ({
    time: p.date,
    value: p.price_usd,
  }));
  const isSynthetic =
    (prices?.points ?? []).some((p) => p.is_synthetic) ||
    HORIZONS.some((h) => forecasts[h]?.is_synthetic);

  return (
    <div className="space-y-6">
      <nav className="text-xs text-terminal-muted">
        <Link href="/" className="hover:text-white">
          Catalog
        </Link>
        <span className="px-1.5">/</span>
        <span className="text-slate-300">{instrument.symbol}</span>
      </nav>

      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            {instrument.name}
          </h1>
          <DataCoverageBadge synthetic={isSynthetic} />
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-terminal-muted">
          <span className="font-mono text-info">{instrument.symbol}</span>
          <span>
            {instrument.asset_class}
            {instrument.category ? ` · ${instrument.category}` : ""}
          </span>
          <span>Released {formatDate(instrument.release_date)}</span>
          <span>MSRP {formatUSD(instrument.msrp_usd)}</span>
          <span className="tnum">{observed.length} daily snapshots</span>
        </div>
      </header>

      {prices === null ? (
        <div className="panel p-6 text-sm">
          <p className="font-medium text-caution">Price history unavailable</p>
          <p className="mt-1 text-terminal-muted">
            Could not load snapshots for this instrument.
          </p>
        </div>
      ) : (
        <ProductView observed={observed} forecasts={forecasts} />
      )}

      {/* Phase 2: Score, Explanation, Risk */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4">
          {scoreData && <ScoreBadge score={scoreData} />}
          {scoreData && scoreData.available && <ScoreBreakdown score={scoreData} />}
        </div>
        <div>
          {explanationData && <WhyPanel explanation={explanationData} />}
        </div>
        <div>
          {riskData && <RiskPanel risk={riskData} />}
        </div>
      </div>
    </div>
  );
}
