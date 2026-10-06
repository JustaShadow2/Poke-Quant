"use client";

import { useEffect, useState } from "react";

import { getBrowserApiBaseUrl } from "@/lib/api";
import { formatUSD } from "@/lib/format";

interface CompareItem {
  instrument_id: string;
  symbol: string;
  name: string;
  release_date: string | null;
  price_usd: number | null;
  score: number | null;
  band: string | null;
  risk_score: number | null;
  risk_level: string | null;
  expected_return: number | null;
  predicted_price: number | null;
}

export default function ComparePage() {
  const [ids, setIds] = useState("");
  const [items, setItems] = useState<CompareItem[]>([]);
  const [loading, setLoading] = useState(false);

  const doCompare = () => {
    if (!ids.trim()) return;
    setLoading(true);
    fetch(`${getBrowserApiBaseUrl()}/api/v1/compare?ids=${encodeURIComponent(ids.trim())}`)
      .then((r) => r.json())
      .then((data) => setItems(data.instruments ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-white">Compare Instruments</h1>

      <div className="flex gap-2">
        <input
          type="text"
          value={ids}
          onChange={(e) => setIds(e.target.value)}
          placeholder="Paste comma-separated instrument IDs"
          className="flex-1 rounded border border-terminal-border bg-terminal-panel px-3 py-2 text-sm text-white placeholder-terminal-muted focus:border-info focus:outline-none"
          onKeyDown={(e) => e.key === "Enter" && doCompare()}
        />
        <button onClick={doCompare} className="rounded bg-info/20 px-4 py-2 text-sm font-medium text-info hover:bg-info/30">
          Compare
        </button>
      </div>

      {loading && <div className="text-sm text-terminal-muted">Loading...</div>}

      {items.length > 0 && (
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-terminal-border text-xs uppercase text-terminal-muted">
                <th className="px-4 py-2 text-left">Metric</th>
                {items.map((item) => (
                  <th key={item.instrument_id} className="px-4 py-2 text-center">
                    <div className="text-slate-200">{item.symbol}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-terminal-border">
              <tr>
                <td className="px-4 py-2 text-terminal-muted">Name</td>
                {items.map((i) => <td key={i.instrument_id} className="px-4 py-2 text-center text-slate-200 text-xs">{i.name}</td>)}
              </tr>
              <tr>
                <td className="px-4 py-2 text-terminal-muted">Price</td>
                {items.map((i) => <td key={i.instrument_id} className="tnum px-4 py-2 text-center text-white">{i.price_usd ? formatUSD(i.price_usd) : "—"}</td>)}
              </tr>
              <tr>
                <td className="px-4 py-2 text-terminal-muted">Score</td>
                {items.map((i) => (
                  <td key={i.instrument_id} className="px-4 py-2 text-center">
                    {i.score != null ? <span className="tnum font-semibold text-white">{i.score.toFixed(0)} <span className="text-xs text-terminal-muted">{i.band}</span></span> : "—"}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-4 py-2 text-terminal-muted">Risk</td>
                {items.map((i) => (
                  <td key={i.instrument_id} className="tnum px-4 py-2 text-center text-terminal-muted">
                    {i.risk_score != null ? `${i.risk_score.toFixed(0)} (${i.risk_level})` : "—"}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-4 py-2 text-terminal-muted">Exp. Return</td>
                {items.map((i) => {
                  const color = (i.expected_return ?? 0) >= 0 ? "text-green-400" : "text-red-400";
                  return (
                    <td key={i.instrument_id} className={`tnum px-4 py-2 text-center font-medium ${color}`}>
                      {i.expected_return != null ? `${(i.expected_return * 100).toFixed(1)}%` : "—"}
                    </td>
                  );
                })}
              </tr>
              <tr>
                <td className="px-4 py-2 text-terminal-muted">Target Price</td>
                {items.map((i) => <td key={i.instrument_id} className="tnum px-4 py-2 text-center text-slate-200">{i.predicted_price ? formatUSD(i.predicted_price) : "—"}</td>)}
              </tr>
              <tr>
                <td className="px-4 py-2 text-terminal-muted">Released</td>
                {items.map((i) => <td key={i.instrument_id} className="px-4 py-2 text-center text-xs text-terminal-muted">{i.release_date ?? "—"}</td>)}
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {items.length === 0 && !loading && (
        <div className="panel p-6 text-sm text-terminal-muted">
          Enter 2-5 instrument IDs (comma-separated) from the catalog to compare them side-by-side.
          Find IDs on the <a href="/" className="text-info hover:underline">catalog page</a> or via the API.
        </div>
      )}
    </div>
  );
}
