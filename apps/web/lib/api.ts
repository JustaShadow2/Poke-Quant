/**
 * Typed client for the PokéQuant API (mirrors apps/api schemas).
 *
 * Server components call these; the base URL resolves from `API_BASE_URL`
 * (server-to-server, e.g. http://api:8000 in Docker) falling back to
 * `NEXT_PUBLIC_API_BASE_URL` and finally localhost for bare `next dev`.
 */

export type Horizon = "d30" | "d90" | "d180" | "d365";

export const HORIZONS: readonly Horizon[] = ["d30", "d90", "d180", "d365"];

export const HORIZON_DAYS: Record<Horizon, number> = {
  d30: 30,
  d90: 90,
  d180: 180,
  d365: 365,
};

export interface InstrumentSummary {
  id: string;
  symbol: string;
  name: string;
  asset_class: string;
  category: string | null;
  release_date: string | null;
  msrp_usd: number | null;
  currency: string;
  is_active: boolean;
}

export interface InstrumentListResponse {
  items: InstrumentSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface PricePoint {
  date: string;
  price_usd: number;
  source: string;
  volume: number | null;
  active_listings: number | null;
  attention_index: number | null;
  is_synthetic: boolean;
}

export interface PriceHistoryResponse {
  instrument_id: string;
  count: number;
  points: PricePoint[];
}

export interface ForecastResponse {
  instrument_id: string;
  horizon: Horizon;
  as_of: string;
  last_price: number;
  predicted_price: number;
  predicted_return: number;
  expected_change_pct: number;
  quantiles_price: Record<string, number>;
  quantiles_return: Record<string, number>;
  model_version: string | null;
  is_synthetic: boolean;
  source: string;
  disclaimer: string | null;
}

export function getApiBaseUrl(): string {
  return (
    process.env.API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://localhost:8000"
  ).replace(/\/$/, "");
}

async function apiGet<T>(path: string): Promise<T | null> {
  const url = `${getApiBaseUrl()}${path}`;
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store" });
  } catch {
    // API unreachable (e.g. during a static build or when the backend is down).
    return null;
  }
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`API ${res.status} for ${path}`);
  }
  return (await res.json()) as T;
}

export async function listInstruments(params?: {
  assetClass?: string;
  limit?: number;
  offset?: number;
}): Promise<InstrumentListResponse | null> {
  const q = new URLSearchParams();
  if (params?.assetClass) q.set("asset_class", params.assetClass);
  q.set("limit", String(params?.limit ?? 100));
  q.set("offset", String(params?.offset ?? 0));
  return apiGet<InstrumentListResponse>(`/api/v1/instruments?${q.toString()}`);
}

export async function getInstrument(id: string): Promise<InstrumentSummary | null> {
  return apiGet<InstrumentSummary>(`/api/v1/instruments/${id}`);
}

export async function getPrices(id: string): Promise<PriceHistoryResponse | null> {
  return apiGet<PriceHistoryResponse>(`/api/v1/instruments/${id}/prices`);
}

export async function getForecast(
  id: string,
  horizon: Horizon,
): Promise<ForecastResponse | null> {
  return apiGet<ForecastResponse>(
    `/api/v1/instruments/${id}/forecast?horizon=${horizon}`,
  );
}

/** Pull median/low/high out of a `{ "0.1": .., "0.5": .., "0.9": .. }` map. */
export function bandFromQuantiles(
  q: Record<string, number>,
): { low: number; median: number; high: number } | null {
  const entries = Object.entries(q)
    .map(([k, v]) => [Number(k), v] as const)
    .filter(([k]) => !Number.isNaN(k))
    .sort((a, b) => a[0] - b[0]);
  if (entries.length === 0) return null;
  const low = entries[0][1];
  const high = entries[entries.length - 1][1];
  const mid = entries.reduce((best, e) =>
    Math.abs(e[0] - 0.5) < Math.abs(best[0] - 0.5) ? e : best,
  );
  return { low, median: mid[1], high };
}
