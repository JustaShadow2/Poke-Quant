# PokéQuant — current progress

Last updated: 2026-08-14

This is the working status file for the repo: what is live, what is blocked, and what to do next. The long-form design still lives in [`docs/`](docs/README.md). The delivery plan is in [`docs/12-roadmap.md`](docs/12-roadmap.md).

## Snapshot

| Area | Status |
|------|--------|
| Design spec (docs 00–13 + ADRs) | Done |
| Phase 1 MVP (sealed catalog, synthetic history, GBM forecast, Docker) | Done |
| Phase 2 (SHAP, Investment Score, Risk Engine, conformal calibration, HPO) | Done |
| Phase 3 (portfolio, watchlists, alerts, scanner, Monte Carlo, similarity, assistant, dashboard, compare, market overview, admin) | Done |
| Phase 4 (drift monitoring, retraining, CI/CD, E2E tests, caching, security, performance, observability, production Docker) | **Done** |
| Phase 5 (second asset class plugin, public API) | Not started |
| Live market ingest (eBay / FRED) | Coded, idle until API keys |
| AI Assistant (Groq free models) | Wired — needs `GROQ_API_KEY` |

**Run it:** `docker compose up --build` → UI [http://localhost:3000](http://localhost:3000) · API [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Phase 4 — Scale & Hardening (Complete)

### Drift Monitoring (`pokequant/ml/drift.py`)
- **Feature drift:** PSI (Population Stability Index) per feature; thresholds at 0.15 warning, 0.25 critical.
- **Prediction drift:** Kolmogorov-Smirnov test (α=0.05) on recent predictions vs training distribution.
- **Calibration drift:** Empirical coverage vs nominal; ±5% tolerance triggers recalibration.
- **DriftReport** with per-feature breakdown, severity, and automated recommendation (monitor / recalibrate / retrain).

### Automated Retraining (`pokequant/pipelines/retraining.py`)
- `check_drift()` → `retrain_if_needed()` pipeline.
- Promotion gates: candidate must beat champion on holdout RMSE + not regress calibration.
- After retrain: automatic conformal recalibration.
- CLI: `pokequant drift-check`, `pokequant retrain`, `pokequant retrain --force`.

### CI/CD (`.github/workflows/ci.yml`)
- **Backend job:** ruff lint + format check → mypy → pytest → pip-audit (non-blocking).
- **Frontend job:** npm ci → typecheck → production build.
- **Docker job:** Buildx multi-platform build (API + Web images) with GHA cache.
- Triggers on push/PR to main.

### E2E Tests (`apps/web/e2e/smoke.spec.ts`)
- Playwright tests for 7 critical flows: Catalog, Product Page, Scanner, Dashboard, Grade Tab, Market Overview, AI Assistant dock.
- Config: Chromium, 30s timeout, retry on first failure with trace.
- Run: `npx playwright test` (requires stack running).

### Redis Caching (`pokequant/api/cache.py`)
- Cache forecasts/scores/risk by `(prefix, instrument_id, horizon)`.
- Graceful degradation: if Redis unavailable, all operations silently no-op.
- Invalidation: per-instrument, per-key, or full flush (called after pipeline runs).
- Default TTL: 1 hour (pipelines invalidate on update anyway).

### Security & Rate Limiting (`pokequant/api/middleware.py`)
- **Rate limiting:** 60 requests/minute per IP (in-memory token bucket). Returns 429 with Retry-After header.
- **Security headers:** X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy.
- **pip-audit** in CI for dependency vulnerability scanning.
- **CORS:** restricted to configured origins (no wildcard in production).

### Performance
- **GZip compression:** responses > 500 bytes compressed automatically.
- **Batch endpoint:** `GET /api/v1/batch/instruments?ids=a,b,c` — fetch forecast/score/risk/explanation for up to 20 instruments in one call.
- **DB indexes:** reviewed; all FK columns and query patterns have indexes from the ORM definitions.

### Observability (`pokequant/api/middleware.py` + health)
- **Structured request logging:** every request logged with method, path, status, duration_ms, request_id.
- **X-Request-ID header:** returned on every response for correlation.
- **Enriched health:** `GET /health/detailed` returns uptime, DB connectivity, Redis status, configured features (Groq/eBay/FRED).

### Production Dockerfile (multi-stage)
- **Builder stage:** installs deps into a virtualenv (clean, no build tools in runtime).
- **Runtime stage:** Python 3.12-slim, only runtime deps (libgomp1 for LightGBM, curl for healthcheck).
- **Non-root:** runs as `appuser` (no root in container).
- **HEALTHCHECK** built into the image (10s interval, 600s start period for bootstrap).

---

## All Phases Summary

### Phase 1 — Foundation
- 15 curated sealed instruments, ~900 days synthetic history
- LightGBM + baselines, walk-forward evaluation
- Product page with price chart + forecast bands
- Grade tab: CNN vision model + PSA ROI calculator
- Docker Compose one-command bring-up

### Phase 2 — ML & Explainability
- Quantile intervals + conformal calibration (CQR)
- SHAP explanations (TreeExplainer + NL narrative)
- Investment Score 0–100 (8 components, 4 profiles, bands)
- Risk Engine (5 factors, probability × severity)
- Optuna HPO
- Frontend: ScoreBadge, WhyPanel, RiskPanel

### Phase 3 — Product & UX
- Portfolio (transactions, FIFO cost basis, P&L)
- Watchlists (CRUD)
- Alerts (5 rule types, evaluation engine, in-app notifications)
- Scanner (rank by score/risk/momentum/return)
- Monte Carlo simulation (10K paths, probability distribution)
- Similarity search (cosine on feature vectors)
- AI Assistant (Groq, 4-model fallback chain, grounded responses)
- Dashboard, Market Overview, Compare, Simulate pages
- Admin/Ops page
- Daily Summary + Portfolio Review (AI-powered) endpoints
- 11 navigation pages + persistent assistant chat dock

### Phase 4 — Scale & Hardening
- Drift monitoring (PSI + KS + calibration coverage)
- Automated retraining with promotion gates
- GitHub Actions CI/CD (lint, type, test, build, audit)
- Playwright E2E tests (7 flows)
- Redis caching with graceful degradation
- Rate limiting (60/min/IP) + security headers
- GZip compression + batch endpoint
- Structured request logging + enriched health check
- Multi-stage production Dockerfile (non-root)

---

## CLI Commands (complete)

```bash
# Data pipeline
pokequant db upgrade          # apply migrations (0001-0003)
pokequant seed                # load instrument catalog
pokequant synth --days 900    # generate synthetic history
pokequant features build      # compute features
pokequant train --horizon d90 # train + register GBM
pokequant forecast run        # batch-forecast all instruments

# Phase 2
pokequant phase2              # calibrate + explain + score + risk
pokequant calibrate           # conformal calibration only
pokequant explain             # SHAP explanations only
pokequant score               # Investment Scores + Risk only

# Phase 4
pokequant drift-check         # run drift detection
pokequant retrain             # check drift + retrain if needed
pokequant retrain --force     # force retrain regardless of drift

# Vision
pokequant vision-train        # train card-grading CNN

# Serve
pokequant serve               # FastAPI on :8000
```

## API Endpoints (full list)

| Path | Method | Tags |
|------|--------|------|
| `/health` | GET | health |
| `/health/detailed` | GET | health |
| `/api/v1/instruments` | GET | catalog |
| `/api/v1/instruments/{id}` | GET | catalog |
| `/api/v1/instruments/{id}/prices` | GET | prices |
| `/api/v1/instruments/{id}/forecast` | GET | forecast |
| `/api/v1/instruments/{id}/explain` | GET | explainability |
| `/api/v1/instruments/{id}/score` | GET | scoring |
| `/api/v1/instruments/{id}/risk` | GET | risk |
| `/api/v1/instruments/{id}/montecarlo` | GET | simulation |
| `/api/v1/instruments/{id}/similar` | GET | similarity |
| `/api/v1/cards/search` | GET | cards |
| `/api/v1/cards/{id}` | GET | cards |
| `/api/v1/cards/vision-grade` | POST | cards |
| `/api/v1/cards/{id}/grade-roi` | POST | cards |
| `/api/v1/portfolio` | GET | portfolio |
| `/api/v1/portfolio/transactions` | GET/POST | portfolio |
| `/api/v1/portfolio/review` | GET | portfolio |
| `/api/v1/watchlists` | GET/POST | watchlist |
| `/api/v1/watchlists/{id}` | GET/DELETE | watchlist |
| `/api/v1/watchlists/{id}/items` | POST | watchlist |
| `/api/v1/watchlists/{id}/items/{iid}` | DELETE | watchlist |
| `/api/v1/alerts/rules` | GET/POST | alerts |
| `/api/v1/alerts/rules/{id}` | DELETE | alerts |
| `/api/v1/alerts/events` | GET | alerts |
| `/api/v1/alerts/events/{id}/read` | POST | alerts |
| `/api/v1/scanner` | GET | scanner |
| `/api/v1/compare` | GET | compare |
| `/api/v1/dashboard` | GET | dashboard |
| `/api/v1/summary` | GET | dashboard |
| `/api/v1/assistant/chat` | POST | assistant |
| `/api/v1/batch/instruments` | GET | batch |

## Frontend Pages

| Route | Description |
|-------|-------------|
| `/` | Catalog (all instruments) |
| `/instruments/[id]` | Product page (chart, forecast, score, explanation, risk) |
| `/dashboard` | Portfolio pulse, opportunities, movers |
| `/scanner` | Ranked instrument table (sortable) |
| `/market` | Market overview (breadth, top by score/return/risk) |
| `/portfolio` | Holdings, transactions, P&L |
| `/watchlist` | Manage watchlists + instruments |
| `/alerts` | Alert rules CRUD + notification feed |
| `/simulate` | Monte Carlo simulation UI |
| `/compare` | Side-by-side instrument comparison |
| `/grade` | Card search, PSA ROI, CNN vision pre-grade |
| `/admin` | System health, pipeline status, CLI reference |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres connection string |
| `REDIS_URL` | Optional | Redis for caching (degrades gracefully without it) |
| `GROQ_API_KEY` | For AI assistant | Groq API key (free tier models) |
| `POKEMONTCG_API_KEY` | Optional | Higher rate limit for card search |
| `EBAY_CLIENT_ID` | Optional | Live sealed product prices |
| `EBAY_CLIENT_SECRET` | Optional | Live sealed product prices |
| `FRED_API_KEY` | Optional | Macro data for risk engine |

---

## What's Left (Phase 5 only)

Phase 5 is the "prove the platform thesis" phase — adding a second asset class as a plugin:
- Second asset-class plugin (e.g., `mtg_sealed` or `sports_cards`)
- Validates that no Pokemon-specific assumptions leaked into the core
- Advanced backtesting/scenario studio
- Public API + documentation
- Billing (if productized)

The project is a strong portfolio piece as-is after Phase 4.
