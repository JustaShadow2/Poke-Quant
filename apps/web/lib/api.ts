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

export interface CardSummary {
  id: string;
  name: string;
  set_name: string;
  set_id: string;
  number: string;
  rarity: string | null;
  artist: string | null;
  image_small: string | null;
  image_large: string | null;
  tcgplayer_url: string | null;
  raw_usd: number | null;
  raw_finish: string | null;
  raw_low: number | null;
  raw_mid: number | null;
  raw_high: number | null;
  prices_updated_at: string | null;
  raw_source: string | null;
  graded_source: string | null;
}

export interface CardSearchResponse {
  query: string;
  count: number;
  items: CardSummary[];
}

export interface GradedPrices {
  raw_usd: number;
  psa9_usd: number;
  psa10_usd: number;
  psa8_usd: number;
  raw_source: string;
  graded_source: string;
  graded_note: string;
}

export interface GradeROI {
  raw_usd: number;
  psa8_usd: number;
  psa9_usd: number;
  psa10_usd: number;
  grading_fee_usd: number;
  shipping_usd: number;
  all_in_cost_usd: number;
  p10: number;
  p9: number;
  p8: number;
  expected_grade_proceeds: number;
  expected_net_vs_raw: number;
  breakeven_p10: number | null;
  verdict: string;
  rationale: string;
  prices_are_estimated: boolean;
  probs_source: string;
}

export interface CardValuationResponse {
  card: CardSummary;
  prices: GradedPrices;
  roi: GradeROI;
}

export interface VisionSubgrade {
  name: string;
  score: number;
  notes: string;
}

export interface VisionGradeResponse {
  predicted_grade: number;
  centering: VisionSubgrade;
  corners: VisionSubgrade;
  edges: VisionSubgrade;
  surface: VisionSubgrade;
  method: string;
  disclaimer: string;
}

export interface VisionROIResponse extends CardValuationResponse {
  vision: VisionGradeResponse;
}

export function getBrowserApiBaseUrl(): string {
  if (typeof window === "undefined") return getApiBaseUrl();
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
  ).replace(/\/$/, "");
}

export async function searchCards(q: string): Promise<CardSearchResponse | null> {
  const params = new URLSearchParams({ q, limit: "12" });
  return apiGet<CardSearchResponse>(`/api/v1/cards/search?${params.toString()}`);
}

export async function getCardValuation(
  id: string,
  gradingFee = 25,
  shipping = 15,
): Promise<CardValuationResponse | null> {
  const params = new URLSearchParams({
    grading_fee: String(gradingFee),
    shipping: String(shipping),
  });
  return apiGet<CardValuationResponse>(`/api/v1/cards/${encodeURIComponent(id)}?${params}`);
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


// ---------------------------------------------------------------------------
// Phase 2: Explainability, Scores, Risk
// ---------------------------------------------------------------------------

export interface FeatureAttribution {
  feature: string;
  value: number;
  shap_value: number;
  direction: string;
}

export interface ExplanationResponse {
  instrument_id: string;
  horizon: string;
  available: boolean;
  message?: string;
  as_of_date?: string;
  base_value?: number;
  top_positive?: FeatureAttribution[];
  top_negative?: FeatureAttribution[];
  narrative?: string;
  attributions?: Record<string, number>;
  model_version_id?: string | null;
}

export interface ScoreComponent {
  name: string;
  percentile: number;
  weight: number;
  contribution: number;
  direction: string;
}

export interface ScoreResponse {
  instrument_id: string;
  horizon: string;
  available: boolean;
  message?: string;
  as_of_date?: string;
  score?: number;
  band?: string;
  raw_score?: number;
  profile?: string;
  components?: ScoreComponent[];
  reprint_penalty?: number;
  risk_penalty?: number;
  data_coverage?: number;
  is_sufficient?: boolean;
}

export interface RiskFactor {
  name: string;
  probability: number;
  severity: number;
  score: number;
  level: string;
  narrative: string;
  data_driven: boolean;
}

export interface RiskResponse {
  instrument_id: string;
  horizon: string;
  available: boolean;
  message?: string;
  as_of_date?: string;
  overall_score?: number;
  overall_level?: string;
  factors?: RiskFactor[];
  narrative?: string;
}

export async function getExplanation(
  id: string,
  horizon: Horizon = "d90",
): Promise<ExplanationResponse | null> {
  return apiGet<ExplanationResponse>(
    `/api/v1/instruments/${id}/explain?horizon=${horizon}`,
  );
}

export async function getScore(
  id: string,
  horizon: Horizon = "d90",
): Promise<ScoreResponse | null> {
  return apiGet<ScoreResponse>(
    `/api/v1/instruments/${id}/score?horizon=${horizon}`,
  );
}

export async function getRisk(
  id: string,
  horizon: Horizon = "d90",
): Promise<RiskResponse | null> {
  return apiGet<RiskResponse>(
    `/api/v1/instruments/${id}/risk?horizon=${horizon}`,
  );
}
