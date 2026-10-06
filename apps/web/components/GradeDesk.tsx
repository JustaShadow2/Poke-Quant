"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  type CardSummary,
  type CardValuationResponse,
  type VisionGradeResponse,
  type VisionROIResponse,
  getBrowserApiBaseUrl,
} from "@/lib/api";
import { deltaClass, formatPct, formatUSD } from "@/lib/format";

const VERDICT_STYLE: Record<string, string> = {
  grade: "border-up/40 bg-up/10 text-up",
  borderline: "border-caution/40 bg-caution/10 text-caution",
  lean_raw: "border-terminal-border bg-terminal-bg text-slate-300",
  sell_raw: "border-down/40 bg-down/10 text-down",
};

const VERDICT_LABEL: Record<string, string> = {
  grade: "Grade it",
  borderline: "Borderline",
  lean_raw: "Lean sell raw",
  sell_raw: "Sell raw",
};

function pct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

export function GradeDesk() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CardSummary[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [fee, setFee] = useState(25);
  const [shipping, setShipping] = useState(15);
  const [valuation, setValuation] = useState<CardValuationResponse | null>(null);
  const [loadingCard, setLoadingCard] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);
  const [vision, setVision] = useState<VisionGradeResponse | null>(null);
  const [visionBusy, setVisionBusy] = useState(false);
  const [visionError, setVisionError] = useState<string | null>(null);
  const frontRef = useRef<HTMLInputElement>(null);
  const backRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      setSearchError(null);
      return;
    }
    const handle = window.setTimeout(async () => {
      setSearching(true);
      setSearchError(null);
      try {
        const params = new URLSearchParams({ q, limit: "12" });
        const res = await fetch(
          `${getBrowserApiBaseUrl()}/api/v1/cards/search?${params.toString()}`,
        );
        if (!res.ok) throw new Error(`Search failed (${res.status})`);
        const body = (await res.json()) as { items: CardSummary[] };
        setResults(body.items);
      } catch (err) {
        setSearchError(err instanceof Error ? err.message : "Search failed");
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 320);
    return () => window.clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    if (!selectedId) {
      setValuation(null);
      return;
    }
    let cancelled = false;
    setLoadingCard(true);
    setCardError(null);
    const params = new URLSearchParams({
      grading_fee: String(fee),
      shipping: String(shipping),
    });
    fetch(
      `${getBrowserApiBaseUrl()}/api/v1/cards/${encodeURIComponent(selectedId)}?${params}`,
    )
      .then(async (res) => {
        if (!res.ok) {
          const body = (await res.json().catch(() => null)) as
            | { detail?: string }
            | null;
          throw new Error(body?.detail || `Could not load card (${res.status})`);
        }
        return (await res.json()) as CardValuationResponse;
      })
      .then((data) => {
        if (!cancelled) setValuation(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setValuation(null);
          setCardError(err instanceof Error ? err.message : "Could not load card");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingCard(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, fee, shipping]);

  const roi = valuation?.roi;
  const netClass = roi ? deltaClass(roi.expected_net_vs_raw) : "text-slate-300";

  const subgrades = useMemo(
    () =>
      vision
        ? [vision.centering, vision.corners, vision.edges, vision.surface]
        : [],
    [vision],
  );

  async function runVision() {
    const front = frontRef.current?.files?.[0];
    if (!front) {
      setVisionError("Add a front photo of the card first.");
      return;
    }
    setVisionBusy(true);
    setVisionError(null);
    try {
      const body = new FormData();
      body.append("front", front);
      const back = backRef.current?.files?.[0];
      if (back) body.append("back", back);
      const base = getBrowserApiBaseUrl();
      if (selectedId) {
        body.append("grading_fee", String(fee));
        body.append("shipping", String(shipping));
        const res = await fetch(
          `${base}/api/v1/cards/${encodeURIComponent(selectedId)}/grade-roi`,
          { method: "POST", body },
        );
        if (!res.ok) throw new Error(`Vision grade failed (${res.status})`);
        const payload = (await res.json()) as VisionROIResponse;
        setVision(payload.vision);
        setValuation(payload);
      } else {
        const res = await fetch(`${base}/api/v1/cards/vision-grade`, {
          method: "POST",
          body,
        });
        if (!res.ok) throw new Error(`Vision grade failed (${res.status})`);
        setVision((await res.json()) as VisionGradeResponse);
      }
    } catch (err) {
      setVisionError(err instanceof Error ? err.message : "Vision grade failed");
    } finally {
      setVisionBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          Grade
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-terminal-muted">
          Search a single card, compare raw vs estimated PSA 9 / PSA 10, and
          decide whether submitting to PSA beats selling raw after fees. Then
          optionally photograph the copy for a heuristic pre-grade.
        </p>
      </section>

      <section className="panel p-4">
        <label className="text-xs uppercase tracking-wide text-terminal-muted">
          Search a card
        </label>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Charizard, Pikachu 025, Prismatic Evolutions…"
          className="mt-2 w-full rounded-md border border-terminal-border bg-terminal-bg px-3 py-2 text-sm text-white outline-none placeholder:text-terminal-muted focus:border-info"
        />
        <p className="mt-2 text-xs text-terminal-muted">
          Live names and raw prices from PokemonTCG.io / TCGPlayer.
          {searching ? " Searching…" : ""}
        </p>
        {searchError ? (
          <p className="mt-2 text-sm text-caution">{searchError}</p>
        ) : null}
        {results.length > 0 ? (
          <ul className="mt-3 divide-y divide-terminal-border/80">
            {results.map((card) => (
              <li key={card.id}>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedId(card.id);
                    setVision(null);
                  }}
                  className={`flex w-full items-center gap-3 px-1 py-2.5 text-left transition-colors hover:bg-white/[0.03] ${
                    selectedId === card.id ? "bg-white/[0.04]" : ""
                  }`}
                >
                  {card.image_small ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={card.image_small}
                      alt=""
                      className="h-14 w-10 rounded-sm object-cover"
                    />
                  ) : (
                    <div className="h-14 w-10 rounded-sm bg-terminal-bg" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-white">{card.name}</div>
                    <div className="truncate text-xs text-terminal-muted">
                      {card.set_name} · #{card.number}
                      {card.rarity ? ` · ${card.rarity}` : ""}
                    </div>
                  </div>
                  <div className="tnum text-sm text-slate-200">
                    {formatUSD(card.raw_usd)}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      {cardError ? (
        <div className="panel p-4 text-sm text-caution">{cardError}</div>
      ) : null}

      {loadingCard && !valuation ? (
        <div className="panel p-6 text-sm text-terminal-muted">Loading prices…</div>
      ) : null}

      {valuation ? (
        <section className="space-y-4">
          <header className="flex flex-wrap items-start gap-4">
            {valuation.card.image_small ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={valuation.card.image_large || valuation.card.image_small}
                alt={valuation.card.name}
                className="h-40 w-28 rounded-md object-cover shadow-lg"
              />
            ) : null}
            <div className="min-w-0 flex-1">
              <h2 className="text-xl font-semibold text-white">
                {valuation.card.name}
              </h2>
              <p className="mt-1 text-sm text-terminal-muted">
                {valuation.card.set_name} · #{valuation.card.number}
                {valuation.card.rarity ? ` · ${valuation.card.rarity}` : ""}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="badge border-up/40 bg-up/10 text-up">
                  raw live · TCGPlayer
                </span>
                <span className="badge border-caution/40 bg-caution/10 text-caution">
                  PSA 9/10 estimated
                </span>
              </div>
            </div>
          </header>

          <div className="grid gap-3 sm:grid-cols-3">
            <PriceKpi
              label="Raw (ungraded)"
              value={formatUSD(valuation.prices.raw_usd)}
              sub={valuation.card.raw_finish ?? "TCGPlayer market"}
            />
            <PriceKpi
              label="Est. PSA 9"
              value={formatUSD(valuation.prices.psa9_usd)}
              sub="model estimate"
            />
            <PriceKpi
              label="Est. PSA 10"
              value={formatUSD(valuation.prices.psa10_usd)}
              sub="model estimate"
            />
          </div>
          <p className="text-xs text-terminal-muted">{valuation.prices.graded_note}</p>

          <div className="panel grid gap-4 p-4 sm:grid-cols-2">
            <label className="text-sm">
              <span className="text-xs uppercase tracking-wide text-terminal-muted">
                PSA grading fee
              </span>
              <input
                type="number"
                min={0}
                value={fee}
                onChange={(e) => setFee(Number(e.target.value) || 0)}
                className="mt-1 w-full rounded-md border border-terminal-border bg-terminal-bg px-3 py-2 tnum text-sm"
              />
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase tracking-wide text-terminal-muted">
                Shipping / insurance (round trip)
              </span>
              <input
                type="number"
                min={0}
                value={shipping}
                onChange={(e) => setShipping(Number(e.target.value) || 0)}
                className="mt-1 w-full rounded-md border border-terminal-border bg-terminal-bg px-3 py-2 tnum text-sm"
              />
            </label>
          </div>

          {roi ? (
            <div className="panel space-y-4 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span
                  className={`badge ${VERDICT_STYLE[roi.verdict] ?? VERDICT_STYLE.borderline}`}
                >
                  {VERDICT_LABEL[roi.verdict] ?? roi.verdict}
                </span>
                <span className={`tnum text-lg font-semibold ${netClass}`}>
                  {formatUSD(roi.expected_net_vs_raw)} vs raw
                </span>
              </div>
              <p className="text-sm text-slate-300">{roi.rationale}</p>
              <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <Stat label="All-in cost" value={formatUSD(roi.all_in_cost_usd)} />
                <Stat
                  label="Expected proceeds if graded"
                  value={formatUSD(roi.expected_grade_proceeds)}
                />
                <Stat label="P(PSA 10)" value={pct(roi.p10)} />
                <Stat label="P(PSA 9)" value={pct(roi.p9)} />
                <Stat
                  label="Break-even PSA 10 rate"
                  value={
                    roi.breakeven_p10 === null ? "—" : formatPct(roi.breakeven_p10 * 100)
                  }
                />
                <Stat
                  label="Probability mix"
                  value={
                    roi.probs_source === "vision_conditioned"
                      ? "vision-conditioned"
                      : "unconditional prior"
                  }
                />
              </dl>
            </div>
          ) : null}
        </section>
      ) : null}

      <section id="vision" className="panel space-y-4 p-4">
        <div>
          <h2 className="text-lg font-semibold text-white">
            Computer-vision pre-grade
          </h2>
          <p className="mt-1 text-sm text-terminal-muted">
            Upload a front photo (back optional). A heuristic scorer estimates
            centering, corners, edges, and surface on a PSA-like 1–10 scale, then
            {selectedId
              ? " re-weights the ROI calculator for this copy."
              : " you can search a card above to fold the estimate into ROI."}
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="text-xs uppercase tracking-wide text-terminal-muted">
              Front
            </span>
            <input
              ref={frontRef}
              type="file"
              accept="image/*"
              className="mt-1 block w-full text-xs text-terminal-muted file:mr-3 file:rounded file:border-0 file:bg-info/20 file:px-3 file:py-1.5 file:text-info"
            />
          </label>
          <label className="text-sm">
            <span className="text-xs uppercase tracking-wide text-terminal-muted">
              Back (optional)
            </span>
            <input
              ref={backRef}
              type="file"
              accept="image/*"
              className="mt-1 block w-full text-xs text-terminal-muted file:mr-3 file:rounded file:border-0 file:bg-info/20 file:px-3 file:py-1.5 file:text-info"
            />
          </label>
        </div>
        <button
          type="button"
          onClick={() => void runVision()}
          disabled={visionBusy}
          className="rounded-md bg-info px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {visionBusy ? "Analyzing…" : "Analyze photo"}
        </button>
        {visionError ? <p className="text-sm text-caution">{visionError}</p> : null}
        {vision ? (
          <div className="space-y-3">
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-semibold text-white tnum">
                {vision.predicted_grade.toFixed(1)}
              </span>
              <span className="text-sm text-terminal-muted">
                predicted grade · {vision.method}
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {subgrades.map((s) => (
                <div key={s.name} className="rounded-md border border-terminal-border p-3">
                  <div className="text-xs uppercase tracking-wide text-terminal-muted">
                    {s.name}
                  </div>
                  <div className="tnum mt-1 text-xl font-semibold text-white">
                    {s.score.toFixed(1)}
                  </div>
                  <p className="mt-1 text-xs text-terminal-muted">{s.notes}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-terminal-muted">{vision.disclaimer}</p>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function PriceKpi({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="panel px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-terminal-muted">{label}</div>
      <div className="tnum mt-1 text-xl font-semibold text-white">{value}</div>
      {sub ? <div className="mt-0.5 text-xs text-terminal-muted">{sub}</div> : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-terminal-muted">{label}</dt>
      <dd className="tnum mt-0.5 text-slate-200">{value}</dd>
    </div>
  );
}
