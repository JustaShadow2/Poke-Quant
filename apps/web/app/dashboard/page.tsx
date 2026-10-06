import Link from "next/link";

import { getApiBaseUrl } from "@/lib/api";
import { formatUSD } from "@/lib/format";

export const dynamic = "force-dynamic";

interface DashboardData {
  portfolio: {
    total_cost: number;
    market_value: number;
    unrealized_pnl: number;
    unrealized_pct: number;
    holdings_count: number;
  };
  top_opportunities: Array<{
    instrument_id: string;
    symbol: string;
    name: string;
    score: number;
    band: string;
    expected_return: number | null;
  }>;
  market_movers: Array<{
    instrument_id: string;
    symbol: string;
    name: string;
    expected_return: number;
    price_usd: number | null;
  }>;
  instruments_count: number;
}

async function fetchDashboard(): Promise<DashboardData | null> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/v1/dashboard`, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function Kpi({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="panel px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-terminal-muted">{label}</div>
      <div className={`tnum mt-1 text-xl font-semibold ${color ?? "text-white"}`}>{value}</div>
      {sub && <div className="tnum mt-0.5 text-xs text-terminal-muted">{sub}</div>}
    </div>
  );
}

export default async function DashboardPage() {
  const data = await fetchDashboard();

  if (!data) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
        <div className="panel p-6 text-sm text-terminal-muted">
          Unable to load dashboard data. Make sure the API is running.
        </div>
      </div>
    );
  }

  const pnlColor = data.portfolio.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">Dashboard</h1>

      {/* Portfolio KPIs */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Portfolio Value" value={formatUSD(data.portfolio.market_value)} sub={`${data.portfolio.holdings_count} holdings`} />
        <Kpi label="Total Cost" value={formatUSD(data.portfolio.total_cost)} />
        <Kpi
          label="Unrealized P&L"
          value={`${data.portfolio.unrealized_pnl >= 0 ? "+" : ""}${formatUSD(data.portfolio.unrealized_pnl)}`}
          sub={`${data.portfolio.unrealized_pct >= 0 ? "+" : ""}${data.portfolio.unrealized_pct.toFixed(1)}%`}
          color={pnlColor}
        />
        <Kpi label="Instruments" value={String(data.instruments_count)} sub="tracked products" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Top Opportunities */}
        <div className="panel">
          <div className="border-b border-terminal-border px-4 py-2 text-sm font-medium text-slate-200">
            Top Opportunities (by Score)
          </div>
          <div className="divide-y divide-terminal-border">
            {data.top_opportunities.map((item, i) => (
              <Link
                key={item.instrument_id}
                href={`/instruments/${item.instrument_id}`}
                className="flex items-center justify-between px-4 py-2.5 transition-colors hover:bg-white/5"
              >
                <div className="flex items-center gap-3">
                  <span className="w-5 text-xs text-terminal-muted">{i + 1}</span>
                  <div>
                    <div className="text-sm text-slate-200">{item.name}</div>
                    <div className="text-xs text-terminal-muted">{item.symbol}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="tnum text-sm font-semibold text-white">{item.score.toFixed(0)}</span>
                  <span className="rounded border border-terminal-border bg-terminal-panel px-1.5 py-0.5 text-xs">
                    {item.band}
                  </span>
                </div>
              </Link>
            ))}
            {data.top_opportunities.length === 0 && (
              <div className="px-4 py-3 text-sm text-terminal-muted">Run <code>pokequant phase2</code> to generate scores.</div>
            )}
          </div>
        </div>

        {/* Market Movers */}
        <div className="panel">
          <div className="border-b border-terminal-border px-4 py-2 text-sm font-medium text-slate-200">
            Market Movers (by Expected Return)
          </div>
          <div className="divide-y divide-terminal-border">
            {data.market_movers.map((item) => {
              const retPct = (item.expected_return * 100).toFixed(1);
              const color = item.expected_return >= 0 ? "text-green-400" : "text-red-400";
              return (
                <Link
                  key={item.instrument_id}
                  href={`/instruments/${item.instrument_id}`}
                  className="flex items-center justify-between px-4 py-2.5 transition-colors hover:bg-white/5"
                >
                  <div>
                    <div className="text-sm text-slate-200">{item.name}</div>
                    <div className="text-xs text-terminal-muted">{item.symbol}</div>
                  </div>
                  <div className="text-right">
                    <div className={`tnum text-sm font-semibold ${color}`}>
                      {item.expected_return >= 0 ? "+" : ""}{retPct}%
                    </div>
                    {item.price_usd && (
                      <div className="tnum text-xs text-terminal-muted">{formatUSD(item.price_usd)}</div>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </div>

      <div className="text-xs text-terminal-muted">
        <Link href="/scanner" className="text-info hover:underline">View full scanner →</Link>
        {" · "}
        <Link href="/portfolio" className="text-info hover:underline">Manage portfolio →</Link>
      </div>
    </div>
  );
}
