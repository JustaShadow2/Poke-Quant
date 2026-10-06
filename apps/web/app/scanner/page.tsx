"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getBrowserApiBaseUrl } from "@/lib/api";

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
  predicted_price: number | null;
}

type SortBy = "score" | "risk" | "momentum" | "return";

export default function ScannerPage() {
  const [items, setItems] = useState<ScannerItem[]>([]);
  const [sortBy, setSortBy] = useState<SortBy>("score");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${getBrowserApiBaseUrl()}/api/v1/scanner?sort_by=${sortBy}&limit=20`)
      .then((r) => r.json())
      .then((data) => setItems(data.items ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [sortBy]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">Scanner</h1>
        <div className="flex items-center gap-1">
          {(["score", "return", "momentum", "risk"] as SortBy[]).map((s) => (
            <button
              key={s}
              onClick={() => setSortBy(s)}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                s === sortBy
                  ? "bg-info/20 text-info"
                  : "text-terminal-muted hover:bg-white/5 hover:text-white"
              }`}
            >
              {s === "return" ? "Exp. Return" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="panel overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-terminal-border text-xs uppercase tracking-wide text-terminal-muted">
              <th className="px-4 py-2 text-left">#</th>
              <th className="px-4 py-2 text-left">Instrument</th>
              <th className="px-4 py-2 text-right">Price</th>
              <th className="px-4 py-2 text-right">Score</th>
              <th className="px-4 py-2 text-right">Risk</th>
              <th className="px-4 py-2 text-right">Exp. Return</th>
              <th className="px-4 py-2 text-right">Target</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-terminal-border">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-terminal-muted">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-terminal-muted">No data. Run the pipeline first.</td></tr>
            ) : (
              items.map((item, i) => {
                const retPct = item.expected_return != null ? (item.expected_return * 100).toFixed(1) : "—";
                const retColor = (item.expected_return ?? 0) >= 0 ? "text-green-400" : "text-red-400";
                return (
                  <tr key={item.instrument_id} className="transition-colors hover:bg-white/5">
                    <td className="px-4 py-2 text-terminal-muted">{i + 1}</td>
                    <td className="px-4 py-2">
                      <Link href={`/instruments/${item.instrument_id}`} className="hover:text-info">
                        <div className="text-slate-200">{item.name}</div>
                        <div className="text-xs text-terminal-muted">{item.symbol}</div>
                      </Link>
                    </td>
                    <td className="tnum px-4 py-2 text-right text-slate-200">
                      {item.price_usd != null ? `$${item.price_usd.toFixed(2)}` : "—"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {item.score != null ? (
                        <span className="tnum font-semibold text-white">{item.score.toFixed(0)}</span>
                      ) : "—"}
                      {item.band && (
                        <span className="ml-1 text-xs text-terminal-muted">{item.band}</span>
                      )}
                    </td>
                    <td className="tnum px-4 py-2 text-right text-terminal-muted">
                      {item.risk != null ? `${item.risk.toFixed(0)}` : "—"}
                    </td>
                    <td className={`tnum px-4 py-2 text-right font-medium ${retColor}`}>
                      {retPct !== "—" ? `${(item.expected_return ?? 0) >= 0 ? "+" : ""}${retPct}%` : "—"}
                    </td>
                    <td className="tnum px-4 py-2 text-right text-slate-300">
                      {item.predicted_price != null ? `$${item.predicted_price.toFixed(2)}` : "—"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
