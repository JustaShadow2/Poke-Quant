import Link from "next/link";

import { getApiBaseUrl } from "@/lib/api";
import { formatUSD } from "@/lib/format";

export const dynamic = "force-dynamic";

interface ScannerItem {
  instrument_id: string;
  symbol: string;
  name: string;
  price_usd: number | null;
  score: number | null;
  band: string | null;
  risk: number | null;
  risk_level: string | null;
  expected_return: number | null;
}

async function fetchScanner(sortBy: string): Promise<ScannerItem[]> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/v1/scanner?sort_by=${sortBy}&limit=15`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return data.items ?? [];
  } catch {
    return [];
  }
}

export default async function MarketOverviewPage() {
  const [byScore, byReturn, byRisk] = await Promise.all([
    fetchScanner("score"),
    fetchScanner("return"),
    fetchScanner("risk"),
  ]);

  // Market breadth: % of instruments with positive expected return.
  const total = byReturn.length;
  const bullish = byReturn.filter(i => (i.expected_return ?? 0) > 0).length;
  const breadth = total > 0 ? ((bullish / total) * 100).toFixed(0) : "—";

  // Average score and risk.
  const scores = byScore.filter(i => i.score != null).map(i => i.score!);
  const avgScore = scores.length > 0 ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(0) : "—";
  const risks = byRisk.filter(i => i.risk != null).map(i => i.risk!);
  const avgRisk = risks.length > 0 ? (risks.reduce((a, b) => a + b, 0) / risks.length).toFixed(0) : "—";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">Market Overview</h1>

      {/* Market KPIs */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="panel px-4 py-3">
          <div className="text-xs uppercase text-terminal-muted">Instruments</div>
          <div className="tnum mt-1 text-xl font-semibold text-white">{total}</div>
          <div className="text-xs text-terminal-muted">tracked products</div>
        </div>
        <div className="panel px-4 py-3">
          <div className="text-xs uppercase text-terminal-muted">Breadth</div>
          <div className="tnum mt-1 text-xl font-semibold text-green-400">{breadth}%</div>
          <div className="text-xs text-terminal-muted">bullish (exp. return &gt; 0)</div>
        </div>
        <div className="panel px-4 py-3">
          <div className="text-xs uppercase text-terminal-muted">Avg Score</div>
          <div className="tnum mt-1 text-xl font-semibold text-white">{avgScore}</div>
          <div className="text-xs text-terminal-muted">cross-sectional mean</div>
        </div>
        <div className="panel px-4 py-3">
          <div className="text-xs uppercase text-terminal-muted">Avg Risk</div>
          <div className="tnum mt-1 text-xl font-semibold text-yellow-400">{avgRisk}</div>
          <div className="text-xs text-terminal-muted">/ 100</div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Top Scores */}
        <div className="panel">
          <div className="border-b border-terminal-border px-4 py-2 text-xs font-medium uppercase text-terminal-muted">
            Highest Score
          </div>
          <div className="divide-y divide-terminal-border">
            {byScore.slice(0, 5).map((item, i) => (
              <Link key={item.instrument_id} href={`/instruments/${item.instrument_id}`}
                className="flex items-center justify-between px-4 py-2 transition-colors hover:bg-white/5">
                <div className="flex items-center gap-2">
                  <span className="w-4 text-xs text-terminal-muted">{i + 1}</span>
                  <span className="text-sm text-slate-200">{item.symbol}</span>
                </div>
                <span className="tnum text-sm font-semibold text-white">{item.score?.toFixed(0) ?? "—"} <span className="text-xs text-terminal-muted">{item.band}</span></span>
              </Link>
            ))}
          </div>
        </div>

        {/* Top Returns */}
        <div className="panel">
          <div className="border-b border-terminal-border px-4 py-2 text-xs font-medium uppercase text-terminal-muted">
            Highest Exp. Return
          </div>
          <div className="divide-y divide-terminal-border">
            {byReturn.slice(0, 5).map((item, i) => {
              const ret = item.expected_return ?? 0;
              const color = ret >= 0 ? "text-green-400" : "text-red-400";
              return (
                <Link key={item.instrument_id} href={`/instruments/${item.instrument_id}`}
                  className="flex items-center justify-between px-4 py-2 transition-colors hover:bg-white/5">
                  <div className="flex items-center gap-2">
                    <span className="w-4 text-xs text-terminal-muted">{i + 1}</span>
                    <span className="text-sm text-slate-200">{item.symbol}</span>
                  </div>
                  <span className={`tnum text-sm font-semibold ${color}`}>{ret >= 0 ? "+" : ""}{(ret * 100).toFixed(1)}%</span>
                </Link>
              );
            })}
          </div>
        </div>

        {/* Lowest Risk */}
        <div className="panel">
          <div className="border-b border-terminal-border px-4 py-2 text-xs font-medium uppercase text-terminal-muted">
            Lowest Risk
          </div>
          <div className="divide-y divide-terminal-border">
            {byRisk.slice(0, 5).map((item, i) => (
              <Link key={item.instrument_id} href={`/instruments/${item.instrument_id}`}
                className="flex items-center justify-between px-4 py-2 transition-colors hover:bg-white/5">
                <div className="flex items-center gap-2">
                  <span className="w-4 text-xs text-terminal-muted">{i + 1}</span>
                  <span className="text-sm text-slate-200">{item.symbol}</span>
                </div>
                <span className="tnum text-sm text-terminal-muted">{item.risk?.toFixed(0) ?? "—"} <span className="text-xs">({item.risk_level})</span></span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="text-xs text-terminal-muted">
        Data refreshed on each pipeline run. <Link href="/scanner" className="text-info hover:underline">Full scanner →</Link>
      </div>
    </div>
  );
}
