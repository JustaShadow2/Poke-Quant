"use client";

import { useEffect, useState } from "react";

import { getBrowserApiBaseUrl } from "@/lib/api";
import { formatUSD } from "@/lib/format";

interface Holding {
  instrument_id: string;
  quantity: number;
  avg_cost: number;
  total_cost: number;
  current_price: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pct: number | null;
}

interface PortfolioData {
  portfolio_id: string;
  name: string;
  total_cost: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pct: number;
  transaction_count: number;
  holdings: Holding[];
}

interface Transaction {
  id: string;
  instrument_id: string;
  side: string;
  quantity: number;
  price_usd: number;
  fees_usd: number;
  transacted_at: string;
  notes: string | null;
}

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [tab, setTab] = useState<"holdings" | "transactions">("holdings");

  useEffect(() => {
    const base = getBrowserApiBaseUrl();
    fetch(`${base}/api/v1/portfolio`).then(r => r.json()).then(setPortfolio).catch(() => {});
    fetch(`${base}/api/v1/portfolio/transactions`).then(r => r.json()).then(d => setTransactions(d.transactions ?? [])).catch(() => {});
  }, []);

  if (!portfolio) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-white">Portfolio</h1>
        <div className="panel p-6 text-sm text-terminal-muted">Loading...</div>
      </div>
    );
  }

  const pnlColor = portfolio.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">Portfolio</h1>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="panel px-4 py-3">
          <div className="text-xs uppercase text-terminal-muted">Market Value</div>
          <div className="tnum mt-1 text-xl font-semibold text-white">{formatUSD(portfolio.market_value)}</div>
        </div>
        <div className="panel px-4 py-3">
          <div className="text-xs uppercase text-terminal-muted">Total Cost</div>
          <div className="tnum mt-1 text-xl font-semibold text-white">{formatUSD(portfolio.total_cost)}</div>
        </div>
        <div className="panel px-4 py-3">
          <div className="text-xs uppercase text-terminal-muted">Unrealized P&L</div>
          <div className={`tnum mt-1 text-xl font-semibold ${pnlColor}`}>
            {portfolio.unrealized_pnl >= 0 ? "+" : ""}{formatUSD(portfolio.unrealized_pnl)}
          </div>
          <div className="tnum text-xs text-terminal-muted">
            {portfolio.unrealized_pct >= 0 ? "+" : ""}{portfolio.unrealized_pct.toFixed(1)}%
          </div>
        </div>
        <div className="panel px-4 py-3">
          <div className="text-xs uppercase text-terminal-muted">Transactions</div>
          <div className="tnum mt-1 text-xl font-semibold text-white">{portfolio.transaction_count}</div>
        </div>
      </div>

      {/* Tab toggle */}
      <div className="flex gap-1">
        <button onClick={() => setTab("holdings")} className={`rounded px-3 py-1.5 text-xs font-medium ${tab === "holdings" ? "bg-info/20 text-info" : "text-terminal-muted hover:text-white"}`}>
          Holdings ({portfolio.holdings.length})
        </button>
        <button onClick={() => setTab("transactions")} className={`rounded px-3 py-1.5 text-xs font-medium ${tab === "transactions" ? "bg-info/20 text-info" : "text-terminal-muted hover:text-white"}`}>
          Transactions ({transactions.length})
        </button>
      </div>

      {tab === "holdings" ? (
        <div className="panel overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-terminal-border text-xs uppercase text-terminal-muted">
                <th className="px-4 py-2 text-left">Instrument</th>
                <th className="px-4 py-2 text-right">Qty</th>
                <th className="px-4 py-2 text-right">Avg Cost</th>
                <th className="px-4 py-2 text-right">Current</th>
                <th className="px-4 py-2 text-right">Market Value</th>
                <th className="px-4 py-2 text-right">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-terminal-border">
              {portfolio.holdings.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-terminal-muted">No holdings. Add transactions via the API.</td></tr>
              ) : portfolio.holdings.map((h) => {
                const plColor = (h.unrealized_pnl ?? 0) >= 0 ? "text-green-400" : "text-red-400";
                return (
                  <tr key={h.instrument_id}>
                    <td className="px-4 py-2 text-slate-200 font-mono text-xs">{h.instrument_id.slice(0, 8)}...</td>
                    <td className="tnum px-4 py-2 text-right text-white">{h.quantity}</td>
                    <td className="tnum px-4 py-2 text-right text-terminal-muted">{formatUSD(h.avg_cost)}</td>
                    <td className="tnum px-4 py-2 text-right text-slate-200">{h.current_price ? formatUSD(h.current_price) : "—"}</td>
                    <td className="tnum px-4 py-2 text-right text-white">{h.market_value ? formatUSD(h.market_value) : "—"}</td>
                    <td className={`tnum px-4 py-2 text-right font-medium ${plColor}`}>
                      {h.unrealized_pnl != null ? `${h.unrealized_pnl >= 0 ? "+" : ""}${formatUSD(h.unrealized_pnl)} (${h.unrealized_pct?.toFixed(1)}%)` : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="panel overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-terminal-border text-xs uppercase text-terminal-muted">
                <th className="px-4 py-2 text-left">Date</th>
                <th className="px-4 py-2 text-left">Side</th>
                <th className="px-4 py-2 text-right">Qty</th>
                <th className="px-4 py-2 text-right">Price</th>
                <th className="px-4 py-2 text-right">Fees</th>
                <th className="px-4 py-2 text-left">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-terminal-border">
              {transactions.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-terminal-muted">No transactions yet.</td></tr>
              ) : transactions.map((t) => (
                <tr key={t.id}>
                  <td className="px-4 py-2 text-terminal-muted text-xs">{new Date(t.transacted_at).toLocaleDateString()}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${t.side === "buy" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                      {t.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="tnum px-4 py-2 text-right text-white">{t.quantity}</td>
                  <td className="tnum px-4 py-2 text-right text-slate-200">{formatUSD(t.price_usd)}</td>
                  <td className="tnum px-4 py-2 text-right text-terminal-muted">{formatUSD(t.fees_usd)}</td>
                  <td className="px-4 py-2 text-xs text-terminal-muted truncate max-w-[120px]">{t.notes ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-terminal-muted">
        Add transactions via <code className="text-slate-300">POST /api/v1/portfolio/transactions</code> or the API docs.
      </p>
    </div>
  );
}
