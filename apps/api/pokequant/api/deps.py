"""FastAPI dependency wiring (composition root for the request scope)."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends
from sqlalchemy.orm import Session

from pokequant.core.config import Settings, get_settings
from pokequant.db.session import get_session
from pokequant.grading.service import GradingService
from pokequant.ml.registry import FileModelRegistry
from pokequant.repositories.catalog import CatalogRepository
from pokequant.repositories.market import SnapshotRepository
from pokequant.repositories.ml_repo import ModelRepository, PredictionRepository
from pokequant.services.catalog_service import CatalogService
from pokequant.services.forecast_service import ForecastService
from pokequant.services.price_service import PriceService


def get_registry(settings: Settings = Depends(get_settings)) -> FileModelRegistry:
    return FileModelRegistry(Path(settings.artifact_dir) / "models")


def get_catalog_service(session: Session = Depends(get_session)) -> CatalogService:
    return CatalogService(CatalogRepository(session))


def get_price_service(session: Session = Depends(get_session)) -> PriceService:
    return PriceService(SnapshotRepository(session))


def get_forecast_service(
    session: Session = Depends(get_session),
    registry: FileModelRegistry = Depends(get_registry),
) -> ForecastService:
    return ForecastService(
        predictions=PredictionRepository(session),
        snapshots=SnapshotRepository(session),
        model_repo=ModelRepository(session),
        registry=registry,
    )


def get_grading_service(settings: Settings = Depends(get_settings)) -> GradingService:
    return GradingService.from_settings(settings)
