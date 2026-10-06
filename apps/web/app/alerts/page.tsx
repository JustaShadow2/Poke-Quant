"use client";

import { useEffect, useState } from "react";

import { getBrowserApiBaseUrl } from "@/lib/api";

interface AlertRule {
  id: string;
  instrument_id: string;
  rule_type: string;
  threshold: number;
  is_active: boolean;
  last_triggered_at: string | null;
}

interface AlertEvent {
  id: string;
  instrument_id: string;
  message: string;
  current_value: number;
  is_read: boolean;
  fired_at: string;
}

const RULE_LABELS: Record<string, string> = {
  price_above: "Price Above",
  price_below: "Price Below",
  score_above: "Score Above",
  score_below: "Score Below",
  risk_above: "Risk Above",
};

export default function AlertsPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [tab, setTab] = useState<"rules" | "events">("events");

  // New rule form
  const [rInstrument, setRInstrument] = useState("");
  const [rType, setRType] = useState("price_above");
  const [rThreshold, setRThreshold] = useState("");

  const base = getBrowserApiBaseUrl();

  const refreshRules = () => {
    fetch(`${base}/api/v1/alerts/rules`).then(r => r.json()).then(d => setRules(d.rules ?? [])).catch(() => {});
  };
  const refreshEvents = () => {
    fetch(`${base}/api/v1/alerts/events`).then(r => r.json()).then(d => setEvents(d.events ?? [])).catch(() => {});
  };

  useEffect(() => { refreshRules(); refreshEvents(); }, []);

  const createRule = async () => {
    if (!rInstrument.trim() || !rThreshold) return;
    await fetch(`${base}/api/v1/alerts/rules`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instrument_id: rInstrument.trim(), rule_type: rType, threshold: parseFloat(rThreshold) }),
    });
    setRInstrument(""); setRThreshold("");
    refreshRules();
  };

  const deleteRule = async (id: string) => {
    await fetch(`${base}/api/v1/alerts/rules/${id}`, { method: "DELETE" });
    refreshRules();
  };

  const markRead = async (id: string) => {
    await fetch(`${base}/api/v1/alerts/events/${id}/read`, { method: "POST" });
    refreshEvents();
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">Alerts</h1>

      {/* Tabs */}
      <div className="flex gap-1">
        <button onClick={() => setTab("events")} className={`rounded px-3 py-1.5 text-xs font-medium ${tab === "events" ? "bg-info/20 text-info" : "text-terminal-muted hover:text-white"}`}>
          Notifications ({events.filter(e => !e.is_read).length} unread)
        </button>
        <button onClick={() => setTab("rules")} className={`rounded px-3 py-1.5 text-xs font-medium ${tab === "rules" ? "bg-info/20 text-info" : "text-terminal-muted hover:text-white"}`}>
          Rules ({rules.length})
        </button>
      </div>

      {tab === "events" ? (
        <div className="panel divide-y divide-terminal-border">
          {events.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-terminal-muted">No alerts fired yet. Create rules and run the pipeline.</div>
          ) : events.map(e => (
            <div key={e.id} className={`flex items-start justify-between px-4 py-3 ${e.is_read ? "opacity-60" : ""}`}>
              <div>
                <p className="text-sm text-slate-200">{e.message}</p>
                <p className="mt-0.5 text-xs text-terminal-muted">
                  {new Date(e.fired_at).toLocaleString()} · Value: {e.current_value.toFixed(2)}
                </p>
              </div>
              {!e.is_read && (
                <button onClick={() => markRead(e.id)} className="ml-3 shrink-0 rounded bg-white/5 px-2 py-1 text-xs text-terminal-muted hover:text-white">
                  Mark read
                </button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {/* Create rule form */}
          <div className="panel px-4 py-3">
            <div className="mb-2 text-xs font-medium uppercase text-terminal-muted">New Rule</div>
            <div className="flex flex-wrap gap-2">
              <input
                type="text" value={rInstrument} onChange={e => setRInstrument(e.target.value)}
                placeholder="Instrument ID"
                className="rounded border border-terminal-border bg-terminal-panel px-3 py-1.5 text-sm text-white placeholder-terminal-muted focus:border-info focus:outline-none w-64"
              />
              <select
                value={rType} onChange={e => setRType(e.target.value)}
                className="rounded border border-terminal-border bg-terminal-panel px-3 py-1.5 text-sm text-white focus:border-info focus:outline-none"
              >
                {Object.entries(RULE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <input
                type="number" value={rThreshold} onChange={e => setRThreshold(e.target.value)}
                placeholder="Threshold"
                className="w-24 rounded border border-terminal-border bg-terminal-panel px-3 py-1.5 text-sm text-white placeholder-terminal-muted focus:border-info focus:outline-none"
              />
              <button onClick={createRule} className="rounded bg-info/20 px-3 py-1.5 text-xs font-medium text-info hover:bg-info/30">
                Create Rule
              </button>
            </div>
          </div>

          {/* Rules list */}
          <div className="panel divide-y divide-terminal-border">
            {rules.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-terminal-muted">No alert rules defined.</div>
            ) : rules.map(r => (
              <div key={r.id} className="flex items-center justify-between px-4 py-2.5">
                <div>
                  <span className="text-sm text-slate-200">{RULE_LABELS[r.rule_type] ?? r.rule_type}</span>
                  <span className="ml-2 tnum text-sm text-white font-medium">{r.threshold}</span>
                  <span className="ml-2 font-mono text-xs text-terminal-muted">{r.instrument_id.slice(0, 8)}...</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs ${r.is_active ? "text-green-400" : "text-terminal-muted"}`}>
                    {r.is_active ? "Active" : "Disabled"}
                  </span>
                  <button onClick={() => deleteRule(r.id)} className="text-xs text-red-400 hover:text-red-300">
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
