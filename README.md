# PokéQuant

**A quantitative research and forecasting platform for alternative assets.** Pokémon sealed product is the first supported asset class; the architecture is asset-class-agnostic by design (Magic: The Gathering, sports cards, watches, comics, and more are future plugins).

Think *Bloomberg Terminal x Zillow Zestimate x Morningstar* for collectible investments: historical price tracking, explainable AI forecasting, a proprietary investment score, a risk engine, portfolio analytics, and an AI research assistant.

> Status: **Phases 1–4 implemented.** Forecasting with calibrated intervals, SHAP explanations, a 0–100 Investment Score, a risk engine, portfolio/watchlists/alerts, a scanner, Monte Carlo simulation, similarity search, a Groq-backed AI research assistant, plus a **Grade tab** for singles (search, PSA 9/10 ROI, CNN photo pre-grade). Living status and roadmap: [`PROGRESS.md`](PROGRESS.md). Full design spec under [`docs/`](docs/README.md).

## Quickstart (Docker — one command)

```bash
docker compose up --build
```

This starts Postgres/TimescaleDB, the API, and the web app. On first boot the API
applies migrations and **bootstraps a full synthetic demo** (seed → synthetic
history → features → train four horizons → forecast), so the UI has data
immediately. Then open:

- Web UI — http://localhost:3000 (Catalog + **Grade**)
- API docs (OpenAPI) — http://localhost:8000/docs
- Health — http://localhost:8000/health

Provider API keys are optional (copy `.env.example` → `.env` to add them); without
them the pipeline runs entirely on the calibrated synthetic backfill. Set
`BOOTSTRAP=0` to skip demo generation, or `BOOTSTRAP=force` to regenerate.

## Local development (without Docker)

The Python core is unit-testable on the host interpreter; runtime target is 3.12.

```bash
make setup                 # create ./.venv and install apps/api (editable, dev extras)
make check                 # ruff lint + format + mypy + pytest

# Full offline pipeline (needs a Postgres/Timescale — e.g. `docker compose up -d db`):
make bootstrap             # migrate → seed → synth → features → train → forecast
make api                   # FastAPI on :8000  (in another shell)

make web-install           # install frontend deps
make web                   # Next.js dev server on :3000
```

`make verify` runs the backend checks plus the frontend typecheck and build.

## Deploy to Render

A [`render.yaml`](render.yaml) blueprint provisions everything (Postgres, Redis,
API, web) in one step:

1. Push this repo to GitHub.
2. In Render, choose **New → Blueprint** and point it at your repo. Render reads
   `render.yaml` and creates the database, Redis, API, and web services.
3. After the first deploy, set these in the dashboard:
   - `pokequant-api` → `CORS_ORIGINS` = your web URL (e.g. `https://pokequant-web.onrender.com`)
   - `pokequant-api` → `GROQ_API_KEY` = your free [Groq key](https://console.groq.com/keys) (enables the AI assistant)
   - `pokequant-web` → `NEXT_PUBLIC_API_BASE_URL` = your API URL (e.g. `https://pokequant-api.onrender.com`)

Notes:
- **Fits the free tier.** PyTorch is an *optional* dependency (the `vision`
  extra). The default Docker build skips it, keeping the image small enough for
  Render's free 512 MB plan. The Grade tab automatically uses the heuristic
  photo scorer instead of the CNN — every other feature is unaffected. To run
  the CNN locally, build with `INSTALL_EXTRAS="[vision]"`.
- Render's managed Postgres has no TimescaleDB extension; migrations are written
  to run on vanilla Postgres, so this works unchanged.
- First boot runs the bootstrap (synthetic data → train → forecast →
  scores/risk), which takes a few minutes. The disk mount keeps artifacts across
  deploys.
- Free Postgres/Redis plans are sufficient for a demo; upgrade the DB plan for
  persistence beyond 90 days.

## Repository layout

```
apps/
  api/     FastAPI + data/ML core (providers, ingestion, features, ML, pipelines, CLI)
  web/     Next.js 15 App Router client (catalog + product page)
docs/      System-design specification (00–13) + ADRs
docker-compose.yml   db + redis + api + web
```

See [`apps/api/README.md`](apps/api/README.md) and [`apps/web/README.md`](apps/web/README.md) for subproject details.

## Documentation

Start with the [documentation index](docs/README.md). The specification is organized as 14 chapters (`00`–`13`) plus Architecture Decision Records under [`docs/adr/`](docs/adr/README.md).

## License and disclaimers

This is a portfolio/research project. It is **not** investment advice. It is not affiliated with, endorsed by, or sponsored by Nintendo, The Pokémon Company, eBay, TCGplayer, PriceCharting, PSA, Reddit, Google, or any other referenced entity. All third-party data is used in accordance with the access model documented in [Data Sources](docs/02-data-sources.md).
