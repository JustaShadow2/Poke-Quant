# Deployment Plan — Free Hosting

This document outlines how to deploy PokéQuant for free using a split architecture. The goal: a live, shareable link that works reliably for portfolio demos and interviews without spending anything.

## Architecture Overview

```
┌─────────────────────┐      ┌──────────────────────────┐      ┌─────────────────┐
│   Vercel (free)     │      │  Hugging Face Spaces     │      │   Neon (free)    │
│                     │      │  (free Docker)           │      │                  │
│   Next.js frontend  │─────▶│  FastAPI + ML backend    │─────▶│  Postgres DB     │
│   SSR / static      │ API  │  PyTorch inference       │ SQL  │  500 MB storage  │
│   CDN + edge        │      │  2 vCPU / 16 GB RAM      │      │  Always-on       │
│                     │      │  Persistent 50 GB disk    │      │                  │
└─────────────────────┘      └──────────────────────────┘      └─────────────────┘
                                        │
                                        ▼
                              ┌────────────────────┐
                              │  Appwrite (GitHub   │
                              │  Student Pack)      │
                              │                    │
                              │  • Auth (Phase 3)  │
                              │  • File storage    │
                              │  • User avatars    │
                              └────────────────────┘
```

## Service Breakdown

### 1. Frontend — Vercel (free)

**Why:** Native Next.js platform, zero-config deploy, global CDN, automatic HTTPS, preview deploys on PRs.

**Free tier includes:**
- Unlimited static/SSR deployments
- 100 GB bandwidth/month
- Serverless functions (for API route proxying if needed)
- Preview deployments on every git push
- Custom domain support

**What runs here:**
- The Next.js app (`apps/web/`)
- Catalog page, product pages, Grade tab UI
- Server components fetch from the HF Spaces backend

**Env vars to set:**
```
NEXT_PUBLIC_API_BASE_URL=https://<your-space>.hf.space
API_BASE_URL=https://<your-space>.hf.space
```

---

### 2. Backend + ML — Hugging Face Spaces (free Docker)

**Why:** Only free platform with enough RAM for PyTorch + model files + persistent disk.

**Free tier includes:**
- 2 vCPU, 16 GB RAM
- Custom Docker image support
- 50 GB persistent storage (model checkpoints survive restarts)
- No auto-sleep (Docker Spaces stay running)
- HTTPS endpoint at `https://<username>-<space-name>.hf.space`
- Git-based deploys (push to HF repo)

**What runs here:**
- FastAPI API server
- PyTorch CNN inference (vision grading)
- LightGBM forecasting models
- Synthetic data generation + model training (on first boot)
- All provider adapters (PokemonTCG.io, eBay, FRED)

**Limitations:**
- No WebSocket support (fine — not needed until Phase 3 alerts)
- Cold start takes ~30s if the Space restarts (rare)
- No cron/scheduler (daily ingest needs an external trigger — see section below)

---

### 3. Database — Neon (free)

**Why:** Serverless Postgres with generous free tier, always-on, and connection pooling built in.

**Free tier includes:**
- 0.5 GB storage (plenty for 15 instruments + synthetic history + features)
- 190 compute hours/month (auto-suspends after 5 min idle, resumes in <1s)
- Connection pooling via PgBouncer (good for serverless patterns)
- Branching (create DB branches for testing)
- One project, 10 branches

**What's stored:**
- Instrument catalog
- Daily snapshots + price observations
- Feature vectors
- Model registry metadata
- Predictions + forecasts

**Key difference from local:** No TimescaleDB extension. For the demo scale (15 instruments, ~900 days synthetic), plain Postgres is fine. Hypertables and continuous aggregates are a scale optimization we don't need at demo volume.

**Connection string format:**
```
postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/pokequant?sslmode=require
```

---

### 4. Appwrite — Auth + Storage (Phase 3, already have it)

**Why you have it:** GitHub Student Developer Pack. **When to use it:** Phase 3 when you add user accounts, portfolios, and watchlists.

**What it handles (later):**
- User registration/login (OAuth2 + email/password)
- Session management
- File storage (card photo uploads, user avatars)
- Possibly push notifications for alerts

**For now:** Not needed. The app works without auth for the demo. Wire it in when you build the portfolio/watchlist features.

---

## Changes Required for Deployment

### Database migrations (drop TimescaleDB dependency)

Create an environment-aware migration that skips TimescaleDB when it's not available:

```python
# In the initial migration, wrap TimescaleDB setup:
import os

def upgrade():
    # Core tables work on plain Postgres
    op.create_table("instruments", ...)
    op.create_table("daily_snapshots", ...)
    # ...

    # TimescaleDB features — only in environments that have the extension
    if os.getenv("ENABLE_TIMESCALEDB", "0") == "1":
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
        op.execute("SELECT create_hypertable('daily_snapshots', 'date')")
```

**What you lose without TimescaleDB:**
- Hypertable auto-partitioning (irrelevant at demo scale)
- Continuous aggregates (not implemented yet)
- Compression policies (not needed under 500 MB)

**What still works exactly the same:**
- All queries, all joins, all indexes
- Feature computation, model training, forecasts
- Everything the user sees

### Dockerfile for HF Spaces

Create `Dockerfile.hf` at the repo root (HF Spaces expects a Dockerfile in the root of the Space repo):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential && rm -rf /var/lib/apt/lists/*

# Python deps (CPU-only PyTorch to save space)
COPY apps/api/pyproject.toml apps/api/
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    -e apps/api/

# App code
COPY apps/api/ apps/api/

# Artifacts directory (HF persistent storage mounts here)
RUN mkdir -p /data/artifacts

ENV ARTIFACT_DIR=/data/artifacts
ENV POKEQUANT_ENV=production
ENV PORT=7860

EXPOSE 7860

# HF Spaces expects port 7860
CMD ["python", "-m", "pokequant.cli", "serve", "--host", "0.0.0.0", "--port", "7860"]
```

### Vercel config

Create `apps/web/vercel.json`:

```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next"
}
```

### Environment variables summary

| Service | Variable | Value |
|---------|----------|-------|
| Vercel | `NEXT_PUBLIC_API_BASE_URL` | `https://<user>-pokequant.hf.space` |
| Vercel | `API_BASE_URL` | `https://<user>-pokequant.hf.space` |
| HF Spaces | `DATABASE_URL` | `postgresql://...@neon.tech/pokequant?sslmode=require` |
| HF Spaces | `ARTIFACT_DIR` | `/data/artifacts` |
| HF Spaces | `CORS_ORIGINS` | `https://pokequant.vercel.app` |
| HF Spaces | `BOOTSTRAP` | `1` |
| HF Spaces | `POKEMONTCG_API_KEY` | (optional) |
| HF Spaces | `EBAY_CLIENT_ID` | (optional, when you get keys) |
| HF Spaces | `FRED_API_KEY` | (optional) |
| Neon | — | Managed via Neon dashboard |

---

## Deployment Steps (in order)

### Step 1: Set up Neon

1. Go to https://neon.tech → sign up (free)
2. Create project "pokequant", region `us-east-2`
3. Copy the connection string
4. Run migrations from your local machine against Neon:
   ```bash
   DATABASE_URL="postgresql://..." make migrate
   DATABASE_URL="postgresql://..." make seed
   ```

### Step 2: Deploy backend to Hugging Face Spaces

1. Go to https://huggingface.co/spaces → Create new Space
2. Choose "Docker" as the SDK
3. Name it `pokequant` (URL becomes `https://<user>-pokequant.hf.space`)
4. In Space settings → "Repository secrets", add:
   - `DATABASE_URL` (from Neon)
   - `CORS_ORIGINS` (your Vercel URL, or `*` initially)
   - `BOOTSTRAP=1`
5. Push your code (HF Spaces uses git):
   ```bash
   # Add HF remote
   git remote add hf https://huggingface.co/spaces/<user>/pokequant
   # Push (HF needs the Dockerfile at repo root)
   git push hf main
   ```
6. Wait for build + bootstrap (~5-8 min first time for model training)
7. Verify: `curl https://<user>-pokequant.hf.space/health`

### Step 3: Deploy frontend to Vercel

1. Go to https://vercel.com → Import Git Repository
2. Set root directory to `apps/web`
3. Add env vars:
   - `NEXT_PUBLIC_API_BASE_URL=https://<user>-pokequant.hf.space`
   - `API_BASE_URL=https://<user>-pokequant.hf.space`
4. Deploy
5. (Optional) Add custom domain in Vercel settings

### Step 4: Verify end-to-end

- [ ] Frontend loads at `https://pokequant.vercel.app` (or your domain)
- [ ] Catalog page shows 15 instruments
- [ ] Product page shows price chart + forecast bands
- [ ] Grade tab: search returns cards from PokemonTCG.io
- [ ] Grade tab: photo upload returns `method: "cnn_v1"` with subscores
- [ ] API docs accessible at `https://<user>-pokequant.hf.space/docs`

---

## Handling Scheduled Jobs (daily ingest)

HF Spaces doesn't have cron. Options for running daily ingestion:

**Option A: GitHub Actions cron (free)**
```yaml
# .github/workflows/daily-ingest.yml
name: Daily Ingest
on:
  schedule:
    - cron: '0 6 * * *'  # 6am UTC daily
jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - run: curl -X POST https://<user>-pokequant.hf.space/api/v1/admin/trigger-ingest
```

Add a simple admin endpoint that triggers the ingest pipeline. Protect it with a secret token.

**Option B: Manual trigger**
For now, just run it when you want fresh data:
```bash
curl -X POST https://<user>-pokequant.hf.space/api/v1/admin/trigger-ingest \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Option C: Ignore it for demo**
The synthetic data is sufficient for portfolio demos. Real ingest only matters once you have eBay/FRED keys and want accumulating history.

---

## Cost Summary

| Service | Cost | What you get |
|---------|------|--------------|
| Vercel | $0 | Frontend hosting, CDN, HTTPS, preview deploys |
| Hugging Face Spaces | $0 | 2 vCPU, 16 GB RAM, Docker, 50 GB disk |
| Neon | $0 | Postgres, 0.5 GB, connection pooling |
| Appwrite (Student Pack) | $0 | Auth + storage for Phase 3 |
| **Total** | **$0** | |

---

## Limitations of the Free Setup

| Limitation | Impact | Workaround |
|-----------|--------|------------|
| Neon auto-suspends after 5 min idle | First request after idle adds ~1s for DB wake | Acceptable for demo; stays warm under any traffic |
| No TimescaleDB | No hypertables/compression | Irrelevant at 15 instruments; add when scaling |
| No Redis | No caching layer | Forecasts are precomputed and stored in Postgres; fine for demo traffic |
| HF Spaces occasional restart | Model reloads in ~10s | Persistent storage keeps checkpoint; fast reload |
| No WebSocket | No real-time alerts | Phase 3 concern; not needed for demo |
| Single region | Latency for distant users | Fine for interviews/portfolio demos |

---

## Upgrade Path

When you outgrow free tier or want production reliability:

1. **Railway ($5/mo):** Drop-in Docker Compose hosting, single command deploy, persistent volumes, multiple services. Best bang for buck.
2. **Render Starter ($7/mo):** Similar to Railway, more polished dashboard.
3. **Full production (Phase 4):** AWS/GCP with Terraform as designed in `docs/01-system-architecture.md` §10 Track B.

The jump from free → $5/mo Railway is the biggest quality-of-life improvement (persistent, no cold starts, Redis included, native Docker Compose). Do it when you start showing the project to employers or want sub-second response times.

---

## Quick Reference

```bash
# Local development (unchanged)
docker compose up --build              # full stack locally
make verify                            # lint + typecheck + test + build

# Deploy to free hosting
# 1. Push migrations to Neon
DATABASE_URL="postgresql://..." make migrate && make seed

# 2. Push to HF Spaces
git push hf main

# 3. Vercel auto-deploys from GitHub on push to main

# Retrain vision model on HF Spaces
curl -X POST https://<user>-pokequant.hf.space/api/v1/admin/vision-retrain
```
