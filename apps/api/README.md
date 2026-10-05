# PokeQuant API (`pokequant`)

Backend for the PokeQuant platform: catalog + market data ingestion, a synthetic
history generator, point-in-time feature engineering, baseline/GBM forecasting
with quantile intervals, and a FastAPI read API.

This is the Phase-1 implementation of the design in [`/docs`](../../docs). See the
repo root [`README.md`](../../README.md) for the quickstart.

## Layout

```
pokequant/
  core/         config, logging, errors, ids (uuid7), clock
  domain/       framework-free enums + value objects
  db/           SQLAlchemy models, session, Alembic migrations
  providers/    PokemonTCG.io / eBay Browse / FRED adapters + rate limiting
  synthetic/    calibrated synthetic history generator
  ingestion/    raw observations -> consolidated daily snapshots
  features/     technical indicators + point-in-time feature builder
  ml/           dataset, baselines, gradient boosting, evaluation, registry
  pipelines/    DB-backed features / training / forecasting
  services/     API-facing application services
  repositories/ repository pattern over SQLAlchemy (+ ports)
  api/          FastAPI app, routers, schemas, DI
  seeds/        curated catalog seed data
  cli.py        Typer CLI (db / seed / synth / ingest / features / train / forecast)
```

## Common commands

```bash
pokequant db upgrade
pokequant seed
pokequant synth --days 900
pokequant features build
pokequant train --horizon d90
pokequant forecast run
pokequant serve --reload
```

Tests: `pytest` (pure-Python core runs without a database).
