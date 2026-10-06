"use client";

import { useState } from "react";

import { getBrowserApiBaseUrl } from "@/lib/api";
import { formatUSD } from "@/lib/format";

interface MCResult {
  last_price: number;
  horizon_days: number;
  n_paths: number;
  expected_return: number;
  volatility: number;
  mean_price: number;
  median_price: number;
  std_price: number;
  percentiles: Record<string, number>;
  prob_positive: number;
  prob_loss_10: number;
  prob_gain_25: number;
  prob_gain_50: number;
  prob_double: number;
  target_probs: Record<string, number>;
}

export default function SimulatePage() {
  const [instrumentId, setInstrumentId] = useState("");
  const [horizon, setHorizon] = useState("d90");
  const [nPaths, setNPaths] = useState(10000);
  const [targetPrice, setTargetPrice] = useState("");
  const [result, setResult] = useState<MCResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    if (!instrumentId.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);

    let url = `${getBrowserApiBaseUrl()}/api/v1/instruments/${instrumentId.trim()}/montecarlo?horizon=${horizon}&n_paths=${nPaths}`;
    if (targetPrice) url += `&target_price=${parseFloat(targetPrice)}`;

    try {
      const res = await fetch(url);
      const data = await res.json();
      if (data.error) { setError(data.error); return; }
      setResult(data);
    } catch { setError("Failed to reach API"); }
    finally { setLoading(false); }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">Monte Carlo Simulation</h1>
      <p className="text-sm text-terminal-muted">
        Simulate 10,000 future price paths using the model&apos;s forecast parameters.
      </p>

      {/* Input form */}
      <div className="panel px-4 py-4 space-y-3">
        <div className="flex flex-wrap gap-3">
          <input type="text" value={instrumentId} onChange={e => setInstrumentId(e.target.value)}
            placeholder="Instrument ID" className="w-72 rounded border border-terminal-border bg-terminal-panel px-3 py-2 text-sm text-white placeholder-terminal-muted focus:border-info focus:outline-none" />
          <select value={horizon} onChange={e => setHorizon(e.target.value)}
            className="rounded border border-terminal-border bg-terminal-panel px-3 py-2 text-sm text-white focus:border-info focus:outline-none">
            <option value="d30">30 days</option>
            <option value="d90">90 days</option>
            <option value="d180">180 days</option>
            <option value="d365">365 days</option>
          </select>
          <input type="number" value={targetPrice} onChange={e => setTargetPrice(e.target.value)}
            placeholder="Target price (opt.)" className="w-36 rounded border border-terminal-border bg-terminal-panel px-3 py-2 text-sm text-white placeholder-terminal-muted focus:border-info focus:outline-none" />
          <button onClick={run} disabled={loading} className="rounded bg-info/20 px-4 py-2 text-sm font-medium text-info hover:bg-info/30 disabled:opacity-50">
            {loading ? "Running..." : "Simulate"}
          </button>
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="panel px-4 py-3">
              <div className="text-xs uppercase text-terminal-muted">Current Price</div>
              <div className="tnum mt-1 text-xl font-semibold text-white">{formatUSD(result.last_price)}</div>
            </div>
            <div className="panel px-4 py-3">
              <div className="text-xs uppercase text-terminal-muted">Mean Outcome</div>
              <div className="tnum mt-1 text-xl font-semibold text-white">{formatUSD(result.mean_price)}</div>
              <div className="text-xs text-terminal-muted">±{formatUSD(result.std_price)}</div>
            </div>
            <div className="panel px-4 py-3">
              <div className="text-xs uppercase text-terminal-muted">Median Outcome</div>
              <div className="tnum mt-1 text-xl font-semibold text-white">{formatUSD(result.median_price)}</div>
            </div>
            <div className="panel px-4 py-3">
              <div className="text-xs uppercase text-terminal-muted">P(Positive)</div>
              <div className={`tnum mt-1 text-xl font-semibold ${result.prob_positive > 0.5 ? "text-green-400" : "text-red-400"}`}>
                {(result.prob_positive * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Probability table */}
          <div className="panel px-4 py-3">
            <div className="mb-2 text-xs font-medium uppercase text-terminal-muted">Probability Distribution</div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm lg:grid-cols-3">
              <div className="flex justify-between">
                <span className="text-terminal-muted">P(loss &gt; 10%)</span>
                <span className="tnum text-red-400">{(result.prob_loss_10 * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-terminal-muted">P(gain &gt; 25%)</span>
                <span className="tnum text-green-400">{(result.prob_gain_25 * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-terminal-muted">P(gain &gt; 50%)</span>
                <span className="tnum text-green-400">{(result.prob_gain_50 * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-terminal-muted">P(double)</span>
                <span className="tnum text-green-400">{(result.prob_double * 100).toFixed(1)}%</span>
              </div>
              {Object.entries(result.target_probs).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-terminal-muted">P({k.replace("above_", "> $")})</span>
                  <span className="tnum text-info">{(v * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>

          {/* Percentile table */}
          <div className="panel px-4 py-3">
            <div className="mb-2 text-xs font-medium uppercase text-terminal-muted">Price Percentiles at Horizon</div>
            <div className="flex flex-wrap gap-4 text-sm">
              {Object.entries(result.percentiles).sort((a, b) => Number(a[0]) - Number(b[0])).map(([pct, val]) => (
                <div key={pct} className="text-center">
                  <div className="text-xs text-terminal-muted">P{pct}</div>
                  <div className="tnum text-white">{formatUSD(val)}</div>
                </div>
              ))}
            </div>
          </div>

          <p className="text-xs text-terminal-muted">
            {result.n_paths.toLocaleString()} paths simulated. Volatility: {(result.volatility * 100).toFixed(1)}% annualized.
            Research only, not investment advice.
          </p>
        </div>
      )}
    </div>
  );
}
