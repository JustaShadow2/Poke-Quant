# 10 — UX Design

PokéQuant should feel like a **financial terminal for collectibles**: dense, fast, dark, data-forward, and trustworthy. This chapter defines the design system, the page inventory with wireframes and component breakdowns, interaction/state patterns, and how explainability and disclaimers are woven throughout.

## 1. Design principles

- **Terminal, not toy.** Information density with clarity; power-user affordances (keyboard nav, command palette) without overwhelming newcomers.
- **Trust through transparency.** Every number is drill-downable to its "why"; uncertainty is always shown (intervals, confidence, data-coverage badges).
- **Progressive disclosure.** A glance gives the verdict (score/forecast); one click reveals the reasoning; another reveals the raw data.
- **Uncertainty is visible, not hidden.** Forecasts show fans/bands, never lone points; synthetic/low-data states are badged.
- **Accessible & responsive.** WCAG AA contrast, keyboard operable, semantic HTML, responsive from ultrawide to mobile.

## 2. Design system

- **Framework:** Next.js + Tailwind + **shadcn/ui** (Radix primitives) for accessible components; **TradingView lightweight-charts** for price/forecast charts; **visx/Recharts** for bespoke analytics (SHAP bars, fans, heatmaps) ([ADR-0009](adr/0009-nextjs-typescript-frontend.md)).
- **Theme:** dark-first ("terminal"), optional light. Neutral slate background, high-contrast text.
- **Semantic color:** green = up/bullish, red = down/bearish, amber = caution/risk, blue = neutral/info. Color is never the *only* signal (icons/labels accompany).
- **Typography:** a clean sans for UI (e.g., Inter), a monospace for numbers/tables so digits align.
- **Density modes:** comfortable vs. compact (power users).
- **Core components:** `ScoreBadge`, `ForecastChart` (price + interval fan), `SparklineCell`, `WhyPanel` (SHAP + components + risks), `RiskMeter`, `ConfidenceBadge`, `DataCoverageBadge` (real vs synthetic), `KpiCard`, `MoversTable`, `CompareMatrix`, `AlertRuleEditor`, `AssistantDock`, `Disclaimer`.
- **Global chrome:** left nav (sections), top bar (global search / command palette `⌘K`, portfolio value, alerts bell, account), persistent **AI assistant dock**, and a persistent research-not-advice disclaimer in the footer.

## 3. Page inventory

Home, Dashboard, Product, Charts, Portfolio, Scanner, Watchlist, Predictions, Risk Analysis, Compare, Market Overview, Settings, Admin. Below: wireframes (ASCII) + component notes. Every data view has explicit **loading / empty / error / low-data** states.

### 3.1 Home (public landing / marketing)

Purpose: explain the platform, show a live sample, drive sign-up; SEO-friendly (SSR).

```
+----------------------------------------------------------------------+
|  PokeQuant           Product  Method  Pricing        [Sign in] [Try] |
+----------------------------------------------------------------------+
|   Quantitative research for alternative assets.                      |
|   Forecasts, scores, and risk -- explained.        [ Explore demo ]  |
|                                                                      |
|   [ Live sample: Prismatic Evolutions ETB  Score 65 (C)  ^+12% 90d ] |
+----------------------------------------------------------------------+
|  How it works: Data -> Features -> Forecast -> Score -> Explain      |
|  [ data sources ] [ methodology ] [ multi-asset vision ]             |
+----------------------------------------------------------------------+
|  Disclaimer: research, not investment advice.                        |
+----------------------------------------------------------------------+
```

### 3.2 Dashboard (authenticated home)

Purpose: personalized snapshot — portfolio pulse, watchlist signals, top opportunities, market context, alerts.

```
+----------------------------------------------------------------------+
| Dashboard                                   [range: 30d v] [refresh] |
+-------------------+-------------------+------------------------------+
| Portfolio Value   | Day / Total P&L   | Portfolio Risk    (Medium)   |
| $12,480  ^+1.8%   | +$220 / +$2,140   | [risk meter ====----]        |
+-------------------+-------------------+------------------------------+
| Watchlist signals                        | Top opportunities (Bal.)  |
|  Lost Origin ETB    Score 78 B  ^+9%     |  1 Obsidian Flames BB  A  |
|  Celebrations UPC   Score 71 B  ~ flat   |  2 151 ETB             A- |
|  Crown Zenith ETB   Score 55 C  v-4%     |  3 Paldea Evolved BB   B+ |
+------------------------------------------+---------------------------+
| Market Overview                              Alerts (3 new)          |
| [ sector index sparkline ]  Breadth 62% up   - Bubble: X overbought  |
| Movers: ^Twilight +14%  vDestined -8%        - Undervalued: Y        |
+----------------------------------------------------------------------+
| [ AI assistant dock: "Review my portfolio" ]                         |
+----------------------------------------------------------------------+
```

Components: `KpiCard` x3, `RiskMeter`, watchlist `MoversTable` w/ `ScoreBadge`+`SparklineCell`, opportunities list, market `KpiCard`+sparkline, alerts feed, `AssistantDock`.

### 3.3 Product page (flagship)

Purpose: everything about one instrument — price history, forecast with intervals, score breakdown, risk, similar/analogues, supply/demand, and the "why." This is the page the whole platform exists to render.

```
+----------------------------------------------------------------------+
| Prismatic Evolutions Elite Trainer Box        [+ Watch] [+ Portfolio]|
| pokemon_sealed / ETB   Released 2025-01   MSRP $49.99   [real data]  |
+----------------------------------------------------------------------+
| Market $118  ^+2.1%    | PQ Score 65 (C)     | Risk  Medium          |
| Fair value $131 (undervalued 10%)            | Confidence  Moderate  |
+----------------------------------------------------------------------+
| Price & Forecast                              [30d][90d][365d][max]   |
|   ^                                                                   |
|   |            observed .....        forecast median ----            |
|   |        ....'''         '''....  ___----  90% band (shaded)       |
|   |   ....'''                     X========------                    |
|   +-------------------------------|now|------------------------> t    |
+----------------------------------------------------------------------+
| Why (score 65)                    | Forecast 90d: +12%  [-6% .. +21%]|
|  + Momentum        +9.8           | Drivers (SHAP):                  |
|  + Expected return +17.2          |  + supply -18% / 90d             |
|  + Supply trend    +10.4          |  + search interest rising        |
|  - Reprint penalty -6.0           |  - valuation vs pack EV          |
|  - Risk drag       -4.5           |  [ full explanation ]            |
+-----------------------------------+----------------------------------+
| Risk factors            | Supply & Demand       | Similar / Analogues |
|  Reprint  55% high      | listings: 340 v       |  Hidden Fates ETB   |
|  Bubble   30% med       | sold/listed: 0.7      |  Lost Origin ETB    |
|  Liquidity 20% low      | search: ^ trending    |  [overlay chart]    |
+-------------------------+-----------------------+---------------------+
| Disclaimer: research, not advice.        [ Ask the assistant about ] |
+----------------------------------------------------------------------+
```

Components: header w/ `DataCoverageBadge`; KPI row (`ScoreBadge`, `RiskMeter`, `ConfidenceBadge`, fair-value gap); `ForecastChart` (observed + median + interval fan, horizon toggles); `WhyPanel` (score components + SHAP drivers, links to [08](08-explainable-ai.md)); risk factor list ([07](07-risk-engine.md)); supply/demand mini-charts; similar/analogue overlay ([09](09-similarity-search.md)); assistant deep-link.

### 3.4 Charts (deep technical view)

Full-screen `ForecastChart` with overlays: moving averages/EMA/Bollinger, RSI/MACD sub-panels, volume/listing-count sub-panel, event markers (release, reprint, set launches), interval fan, and analogue overlay toggle. Crosshair readouts in monospace; export.

### 3.5 Portfolio

Purpose: holdings, cost basis, P&L, allocation, portfolio-level risk, and an AI review.

```
+----------------------------------------------------------------------+
| Portfolio: Main                 Value $12,480  ^+1.8%   [+ Add txn]   |
+----------------------------------------------------------------------+
| Allocation (by category)      | Risk: Medium  Concentration: High    |
|  [donut] ETB 46% BB 30% UPC.. | Diversification: 6 eff. of 11        |
+-------------------------------+--------------------------------------+
| Holdings                                                             |
|  Name              Qty  AvgCost  Mkt   P&L      Score  Risk  Fcst90  |
|  Lost Origin ETB    3   $52      $71   +$57 B   78 B   Low   ^+9%    |
|  151 Booster Box    1   $150     $172  +$22     72 B   Med   ^+6%    |
|  Crown Zenith ETB   4   $41      $39   -$8      55 C   Med   v-4%    |
+----------------------------------------------------------------------+
| [ AI Portfolio Review ]  -> exposure, risks, rebalancing ideas       |
+----------------------------------------------------------------------+
```

Components: `KpiCard`s, allocation donut, correlation/diversification callout ([07 §6](07-risk-engine.md#6-portfolio-level-risk)), holdings table (sortable, each row → product page), transaction entry modal, `AssistantDock` review action.

### 3.6 Scanner (undervalued / opportunity finder)

Purpose: screen the universe by score, fair-value gap, risk, momentum, category, lifecycle. The "alpha discovery" surface.

```
+----------------------------------------------------------------------+
| Scanner   Profile:[Balanced v]  Filters: [category][release][risk<]  |
+----------------------------------------------------------------------+
| Sort: [ Undervaluation v ]                        423 results        |
|  Name              Score  FairGap  Risk   Mom90  Liq   Fcst90        |
|  Obsidian Flames BB  A     +19%    Low    ^+15%  High  ^+14% [-2,+27]|
|  151 ETB             A-    +14%    Med    ^+11%  Med   ^+10%         |
|  Paldea Evolved BB   B+    +9%     Low    ^+7%   High  ^+6%          |
+----------------------------------------------------------------------+
| [ Save as watchlist ]  [ Create alert from filter ]                  |
+----------------------------------------------------------------------+
```

Components: filter bar, results table with `ScoreBadge`/`SparklineCell`/`ConfidenceBadge`, saved-screen presets, "create alert from this screen."

### 3.7 Watchlist

Compact tracked-instrument table (score, price, forecast, risk, alert toggles) with per-item alert quick-config; multiple named watchlists.

### 3.8 Predictions

A dedicated view of a model's forecasts across the universe/horizon: sortable by expected return / confidence, with the interval fan inline and a link to methodology ([05](05-machine-learning.md)); filter by data-coverage (hide synthetic).

### 3.9 Risk Analysis

Per-instrument deep risk view: each factor with probability × severity bars, the driving signals, historical precedents/analogues, and the aggregate risk meter ([07](07-risk-engine.md)); plus a market-wide risk/"bubble radar."

### 3.10 Compare

Side-by-side matrix of 2–4 instruments across score components, forecast, risk factors, supply/demand, and overlaid lifecycle-aligned trajectories ([09](09-similarity-search.md)).

```
+----------------------------------------------------------------------+
| Compare:  [Prismatic ETB] [Hidden Fates ETB] [Lost Origin ETB] [+]   |
+----------------------------------------------------------------------+
|                     Prismatic    Hidden Fates   Lost Origin          |
| PQ Score            65 (C)       81 (A)         78 (B)               |
| Forecast 90d        +12%         +7%            +9%                  |
| Reprint risk        55%          20%            35%                  |
| Months since rel.   14           64             40                  |
| [ overlaid lifecycle-aligned price trajectories ]                    |
+----------------------------------------------------------------------+
```

### 3.11 Market Overview

Purpose: the "index" view — sector/set indices, breadth, movers, liquidity heatmap, archetype clusters, aggregate risk/bubble radar.

```
+----------------------------------------------------------------------+
| Market Overview                                    [range: 90d v]    |
+----------------------------------------------------------------------+
| Sealed Index  ^+6.2% (90d)   Breadth 62% advancing  Bubble radar: Med|
| [ index line chart ]                                                 |
+-------------------------------+--------------------------------------+
| Top movers ^                  | Top movers v                        |
|  Twilight Masq BB  +14%       |  Destined Rivals ETB  -8%           |
+-------------------------------+--------------------------------------+
| Liquidity heatmap (category x turnover)   | Archetypes (clusters)    |
| [ heatmap ]                               | modern-hype / vintage... |
+----------------------------------------------------------------------+
```

### 3.12 Settings

Account/profile, scoring **profile** default (Balanced/Value/Momentum/Conservative — [06 §4](06-investment-score.md#4-default-weights-and-profiles)), notification channels, API keys, theme/density, data/privacy.

### 3.13 Admin / Ops dashboard

Purpose: operator visibility into the pipeline and models (internal).

```
+----------------------------------------------------------------------+
| Admin                                                                |
+----------------------------------------------------------------------+
| Ingestion health                | Model registry                    |
|  pokemontcg  OK  20k/20k budget  |  sealed_forecaster d90 v12 PROD   |
|  ebay_browse OK  4.1k/5k         |   RMSE .. cov 89%  [promote v13?] |
|  reddit      WARN 3 errors       |  drift: features OK, target OK    |
|  trends      DEGRADED (pytrends) |                                   |
+----------------------------------+-----------------------------------+
| Data quality flags: 4 gaps, 1 spike     Provider runs (last 24h)     |
| Job queue: ingest 0, features 0, infer 2                             |
+----------------------------------------------------------------------+
```

Components: provider health cards (from `provider_runs` — [03 §12](03-database-design.md#12-operations)), model registry/drift panels ([05 §9](05-machine-learning.md#9-model-lifecycle--registry)), data-quality flags, queue depths, audit log viewer.

## 4. Cross-cutting interaction patterns

- **Command palette (`⌘K`)** — jump to any instrument/page/action.
- **Everything is drill-downable** — a score/forecast opens its `WhyPanel`; a driver opens the feature; an analogue opens its product page.
- **States** — every async view has skeleton loaders, empty states with guidance, actionable error states, and a **low-data/synthetic badge** where applicable.
- **Real-time-ish** — WebSocket pushes for price/score updates and alerts; otherwise polite polling.
- **Assistant everywhere** — the dock is context-aware (knows the instrument/page you're on) and answers only from computed facts ([11](11-ai-features.md)).
- **Disclaimers** — persistent research-not-advice footer; stronger inline disclaimer on any "buy/sell"-adjacent surface.

## 5. Accessibility & performance

- Semantic, keyboard-operable components (Radix/shadcn); AA contrast; reduced-motion honoring; screen-reader labels on charts (data tables as fallback).
- SSR/ISR for public/product pages (SEO + fast first paint); client-side data fetching via TanStack Query with cache; charts virtualized for large series; p95 latency budgets enforced ([00 §8](00-overview.md#8-success-metrics)).

Continue to [11 — AI Features](11-ai-features.md).
