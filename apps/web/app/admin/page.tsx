import { getApiBaseUrl } from "@/lib/api";

export const dynamic = "force-dynamic";

interface HealthData {
  status: string;
  version: string;
  env: string;
}

async function fetchHealth(): Promise<HealthData | null> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/health`, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

async function fetchDashboard(): Promise<Record<string, any> | null> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/v1/dashboard`, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export default async function AdminPage() {
  const [health, dashboard] = await Promise.all([fetchHealth(), fetchDashboard()]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">Admin / Ops</h1>

      {/* System Health */}
      <div className="panel px-4 py-3">
        <div className="mb-2 text-xs font-medium uppercase text-terminal-muted">System Health</div>
        {health ? (
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-terminal-muted">Status:</span>
              <span className="ml-2 text-green-400 font-medium">{health.status}</span>
            </div>
            <div>
              <span className="text-terminal-muted">Version:</span>
              <span className="ml-2 text-white">{health.version}</span>
            </div>
            <div>
              <span className="text-terminal-muted">Env:</span>
              <span className="ml-2 text-white">{health.env}</span>
            </div>
          </div>
        ) : (
          <p className="text-sm text-red-400">API unreachable</p>
        )}
      </div>

      {/* Pipeline Status */}
      <div className="panel px-4 py-3">
        <div className="mb-2 text-xs font-medium uppercase text-terminal-muted">Data Pipeline</div>
        {dashboard ? (
          <div className="grid grid-cols-2 gap-4 text-sm lg:grid-cols-4">
            <div>
              <div className="text-terminal-muted">Instruments</div>
              <div className="tnum text-lg font-semibold text-white">{dashboard.instruments_count ?? 0}</div>
            </div>
            <div>
              <div className="text-terminal-muted">Opportunities</div>
              <div className="tnum text-lg font-semibold text-white">{dashboard.top_opportunities?.length ?? 0}</div>
            </div>
            <div>
              <div className="text-terminal-muted">Holdings</div>
              <div className="tnum text-lg font-semibold text-white">{dashboard.portfolio?.holdings_count ?? 0}</div>
            </div>
            <div>
              <div className="text-terminal-muted">Market Value</div>
              <div className="tnum text-lg font-semibold text-white">
                ${(dashboard.portfolio?.market_value ?? 0).toFixed(0)}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-terminal-muted">No dashboard data</p>
        )}
      </div>

      {/* CLI Commands */}
      <div className="panel px-4 py-3">
        <div className="mb-2 text-xs font-medium uppercase text-terminal-muted">Operations (run from CLI or container)</div>
        <div className="space-y-1.5 text-sm font-mono">
          <div className="flex items-center gap-3">
            <span className="text-terminal-muted">Ingest:</span>
            <code className="text-slate-300">pokequant ingest</code>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-terminal-muted">Retrain:</span>
            <code className="text-slate-300">pokequant train --horizon d90</code>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-terminal-muted">Forecast:</span>
            <code className="text-slate-300">pokequant forecast run</code>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-terminal-muted">Phase 2:</span>
            <code className="text-slate-300">pokequant phase2</code>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-terminal-muted">Vision:</span>
            <code className="text-slate-300">pokequant vision-train</code>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-terminal-muted">Full:</span>
            <code className="text-slate-300">docker compose exec api pokequant phase2</code>
          </div>
        </div>
      </div>

      {/* Links */}
      <div className="panel px-4 py-3">
        <div className="mb-2 text-xs font-medium uppercase text-terminal-muted">Quick Links</div>
        <div className="flex flex-wrap gap-3 text-sm">
          <a href={`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/docs`}
            target="_blank" rel="noopener noreferrer" className="text-info hover:underline">
            API Docs (OpenAPI)
          </a>
          <a href={`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/health`}
            target="_blank" rel="noopener noreferrer" className="text-info hover:underline">
            Health Check
          </a>
        </div>
      </div>
    </div>
  );
}
