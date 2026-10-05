"""PokeQuant command-line interface (data + ML operations).

pokequant db upgrade          # apply migrations
pokequant seed                # load the curated catalog
pokequant synth --days 900    # generate synthetic history (offline)
pokequant ingest              # live provider pass (uses keys if present)
pokequant features build      # build + store point-in-time features
pokequant train --horizon d90 # train + register forecasters
pokequant forecast run        # batch-forecast all instruments
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

# Silence a benign joblib core-count probe on some macOS setups.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))

import typer

if TYPE_CHECKING:
    from alembic.config import Config

from pokequant.core.clock import today
from pokequant.core.config import get_settings
from pokequant.core.logging import configure_logging, get_logger
from pokequant.domain.enums import Horizon

app = typer.Typer(help="PokeQuant data & ML operations.", no_args_is_help=True)
db_app = typer.Typer(help="Database migrations.")
features_app = typer.Typer(help="Feature engineering.")
forecast_app = typer.Typer(help="Forecasting.")
app.add_typer(db_app, name="db")
app.add_typer(features_app, name="features")
app.add_typer(forecast_app, name="forecast")

log = get_logger("cli")


def _bootstrap_logging() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)


def _alembic_config() -> Config:
    from alembic.config import Config

    import pokequant.db as db_pkg

    migrations = Path(db_pkg.__file__).parent / "migrations"
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    return cfg


@db_app.command("upgrade")
def db_upgrade(revision: str = typer.Argument("head")) -> None:
    """Apply migrations up to REVISION (default: head)."""
    from alembic import command

    _bootstrap_logging()
    command.upgrade(_alembic_config(), revision)
    typer.echo(f"Migrated to {revision}.")


@db_app.command("downgrade")
def db_downgrade(revision: str = typer.Argument("-1")) -> None:
    """Roll back migrations to REVISION."""
    from alembic import command

    _bootstrap_logging()
    command.downgrade(_alembic_config(), revision)
    typer.echo(f"Downgraded to {revision}.")


@app.command()
def seed() -> None:
    """Seed asset classes, categories and the curated instrument catalog."""
    from pokequant.db.session import session_scope
    from pokequant.seeds.loader import seed_catalog

    _bootstrap_logging()
    with session_scope() as session:
        result = seed_catalog(session)
    typer.echo(f"Seeded {result['instruments']} instruments / {result['categories']} categories.")


@app.command()
def synth(
    days: int = typer.Option(1095, help="How many days of history to simulate."),
    asset_class: str = typer.Option("pokemon"),
) -> None:
    """Generate calibrated synthetic price history (offline)."""
    from pokequant.db.session import session_scope
    from pokequant.ingestion.service import IngestionService

    _bootstrap_logging()
    end = today()
    start = end - timedelta(days=days)
    with session_scope() as session:
        result = IngestionService(session).synthetic_backfill(
            asset_class=asset_class, end=end, start=start
        )
    typer.echo(
        f"Synthetic backfill: {result['snapshots']} snapshots / "
        f"{result['observations']} observations for {result['instruments']} instruments."
    )


@app.command()
def ingest(asset_class: str = typer.Option("pokemon")) -> None:
    """Run a live provider ingestion pass (requires API keys; else skipped)."""
    from pokequant.db.session import session_scope
    from pokequant.ingestion.service import IngestionService
    from pokequant.providers.ebay_browse import EbayBrowseProvider
    from pokequant.providers.fred import FredProvider
    from pokequant.providers.ratelimit import RateLimiterRegistry

    _bootstrap_logging()
    settings = get_settings()
    limiters = RateLimiterRegistry()
    market = []
    if settings.ebay_client_id and settings.ebay_client_secret:
        market.append(
            EbayBrowseProvider(
                settings.ebay_client_id,
                settings.ebay_client_secret,
                marketplace_id=settings.ebay_marketplace_id,
                rate_limiter=limiters.register("ebay", 5, 10),
            )
        )
    macro = FredProvider(settings.fred_api_key, rate_limiter=limiters.register("fred", 5, 10))

    with session_scope() as session:
        result = IngestionService(session).ingest_live(
            market, macro if macro.available() else None, asset_class=asset_class
        )
    typer.echo(f"Live ingest: {result}")


@features_app.command("build")
def features_build(asset_class: str = typer.Option("pokemon")) -> None:
    """Build and store the latest point-in-time features per instrument."""
    from pokequant.db.session import session_scope
    from pokequant.pipelines.features import build_and_store_features

    _bootstrap_logging()
    with session_scope() as session:
        result = build_and_store_features(session, asset_class=asset_class)
    typer.echo(f"Features: stored {result['stored']} rows for {result['instruments']} instruments.")


@app.command()
def train(
    horizon: str = typer.Option("d90", help="Forecast horizon: d30|d90|d180|d365."),
    asset_class: str = typer.Option("pokemon"),
    n_splits: int = typer.Option(4, help="Walk-forward folds."),
) -> None:
    """Train baseline + GBM forecasters, evaluate, and register the production model."""
    from pokequant.db.session import session_scope
    from pokequant.ml.registry import FileModelRegistry
    from pokequant.pipelines.training import train_models

    _bootstrap_logging()
    settings = get_settings()
    registry = FileModelRegistry(Path(settings.artifact_dir) / "models")
    with session_scope() as session:
        report = train_models(
            session, registry, horizon=Horizon(horizon), asset_class=asset_class, n_splits=n_splits
        )
    typer.echo(report.summary())


@forecast_app.command("run")
def forecast_run(
    horizon: str = typer.Option("d90"),
    asset_class: str = typer.Option("pokemon"),
) -> None:
    """Batch-forecast all instruments with the production model and store predictions."""
    from pokequant.db.session import session_scope
    from pokequant.ml.registry import FileModelRegistry
    from pokequant.pipelines.forecasting import run_forecasts

    _bootstrap_logging()
    settings = get_settings()
    registry = FileModelRegistry(Path(settings.artifact_dir) / "models")
    with session_scope() as session:
        result = run_forecasts(session, registry, horizon=Horizon(horizon), asset_class=asset_class)
    typer.echo(f"Forecasts written: {result['forecasts']} (model {result['model_version']}).")


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """Run the API with uvicorn."""
    import uvicorn

    uvicorn.run("pokequant.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
