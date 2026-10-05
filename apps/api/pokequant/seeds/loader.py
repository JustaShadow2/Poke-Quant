"""Idempotent catalog seeding from the curated JSON file."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from pokequant.core.logging import get_logger
from pokequant.repositories.catalog import CatalogRepository

log = get_logger(__name__)

DEFAULT_SEED_FILE = Path(__file__).with_name("pokemon_sealed.json")


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d").date()


def seed_catalog(session: Session, *, path: Optional[Path] = None) -> dict[str, Any]:
    payload = json.loads((path or DEFAULT_SEED_FILE).read_text())
    repo = CatalogRepository(session)

    ac_spec = payload["asset_class"]
    asset_class = repo.upsert_asset_class(ac_spec["slug"], ac_spec["name"])

    category_names: dict[str, str] = payload.get("categories", {})
    categories = {
        slug: repo.upsert_category(asset_class.id, slug, name)
        for slug, name in category_names.items()
    }

    count = 0
    for spec in payload["instruments"]:
        category = categories.get(spec["category"])
        msrp = spec.get("msrp_usd")
        inst = repo.upsert_instrument(
            asset_class_id=asset_class.id,
            category_id=category.id if category else None,
            symbol=spec["symbol"],
            name=spec["name"],
            release_date=_parse_date(spec.get("release_date")),
            msrp_usd=Decimal(str(msrp)) if msrp is not None else None,
            attributes=spec.get("attributes", {}),
        )
        for source, external_id in spec.get("identifiers", {}).items():
            repo.upsert_identifier(inst.id, source, external_id)
        count += 1

    log.info("catalog_seeded", asset_class=asset_class.slug, instruments=count)
    return {"asset_class": asset_class.slug, "categories": len(categories), "instruments": count}
