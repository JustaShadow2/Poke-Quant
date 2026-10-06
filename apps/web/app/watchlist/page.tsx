"use client";

import { useEffect, useState } from "react";

import { getBrowserApiBaseUrl } from "@/lib/api";

interface WatchlistSummary {
  id: string;
  name: string;
  created_at: string;
}

interface WatchlistItem {
  instrument_id: string;
  added_at: string;
}

interface WatchlistDetail {
  id: string;
  name: string;
  items: WatchlistItem[];
}

export default function WatchlistPage() {
  const [watchlists, setWatchlists] = useState<WatchlistSummary[]>([]);
  const [selected, setSelected] = useState<WatchlistDetail | null>(null);
  const [newName, setNewName] = useState("");
  const [addId, setAddId] = useState("");

  const base = getBrowserApiBaseUrl();

  const refresh = () => {
    fetch(`${base}/api/v1/watchlists`).then(r => r.json()).then(d => setWatchlists(d.watchlists ?? [])).catch(() => {});
  };

  useEffect(() => { refresh(); }, []);

  const createWatchlist = async () => {
    if (!newName.trim()) return;
    await fetch(`${base}/api/v1/watchlists`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName.trim() }),
    });
    setNewName("");
    refresh();
  };

  const selectWatchlist = async (id: string) => {
    const res = await fetch(`${base}/api/v1/watchlists/${id}`);
    const data = await res.json();
    setSelected(data);
  };

  const deleteWatchlist = async (id: string) => {
    await fetch(`${base}/api/v1/watchlists/${id}`, { method: "DELETE" });
    if (selected?.id === id) setSelected(null);
    refresh();
  };

  const addInstrument = async () => {
    if (!selected || !addId.trim()) return;
    await fetch(`${base}/api/v1/watchlists/${selected.id}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instrument_id: addId.trim() }),
    });
    setAddId("");
    selectWatchlist(selected.id);
  };

  const removeInstrument = async (instrumentId: string) => {
    if (!selected) return;
    await fetch(`${base}/api/v1/watchlists/${selected.id}/items/${instrumentId}`, { method: "DELETE" });
    selectWatchlist(selected.id);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">Watchlists</h1>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Watchlist list */}
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="text" value={newName} onChange={e => setNewName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && createWatchlist()}
              placeholder="New watchlist name"
              className="flex-1 rounded border border-terminal-border bg-terminal-panel px-3 py-2 text-sm text-white placeholder-terminal-muted focus:border-info focus:outline-none"
            />
            <button onClick={createWatchlist} className="rounded bg-info/20 px-3 py-2 text-xs font-medium text-info hover:bg-info/30">
              Create
            </button>
          </div>

          <div className="panel divide-y divide-terminal-border">
            {watchlists.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-terminal-muted">No watchlists yet.</div>
            ) : watchlists.map(wl => (
              <div key={wl.id} className={`flex items-center justify-between px-4 py-2.5 cursor-pointer transition-colors ${selected?.id === wl.id ? "bg-info/10" : "hover:bg-white/5"}`}>
                <button onClick={() => selectWatchlist(wl.id)} className="text-sm text-slate-200 text-left flex-1">
                  {wl.name}
                </button>
                <button onClick={() => deleteWatchlist(wl.id)} className="text-xs text-red-400 hover:text-red-300 ml-2">
                  Delete
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Selected watchlist detail */}
        <div className="lg:col-span-2">
          {selected ? (
            <div className="panel">
              <div className="border-b border-terminal-border px-4 py-2.5 flex items-center justify-between">
                <span className="text-sm font-medium text-white">{selected.name}</span>
                <span className="text-xs text-terminal-muted">{selected.items.length} items</span>
              </div>

              <div className="px-4 py-3">
                <div className="flex gap-2 mb-3">
                  <input
                    type="text" value={addId} onChange={e => setAddId(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && addInstrument()}
                    placeholder="Instrument ID to add"
                    className="flex-1 rounded border border-terminal-border bg-terminal-panel px-3 py-1.5 text-sm text-white placeholder-terminal-muted focus:border-info focus:outline-none"
                  />
                  <button onClick={addInstrument} className="rounded bg-green-500/20 px-3 py-1.5 text-xs font-medium text-green-400 hover:bg-green-500/30">
                    + Add
                  </button>
                </div>

                {selected.items.length === 0 ? (
                  <p className="text-sm text-terminal-muted">Empty watchlist. Add instruments by ID.</p>
                ) : (
                  <div className="space-y-1">
                    {selected.items.map(item => (
                      <div key={item.instrument_id} className="flex items-center justify-between rounded px-3 py-2 hover:bg-white/5">
                        <div>
                          <span className="font-mono text-xs text-slate-300">{item.instrument_id.slice(0, 8)}...</span>
                          <span className="ml-2 text-xs text-terminal-muted">added {new Date(item.added_at).toLocaleDateString()}</span>
                        </div>
                        <button onClick={() => removeInstrument(item.instrument_id)} className="text-xs text-red-400 hover:text-red-300">
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="panel p-6 text-center text-sm text-terminal-muted">
              Select a watchlist or create one to get started.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
