"""Provider-run repository (ingestion observability)."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from pokequant.core.clock import utcnow
from pokequant.db.models import ProviderRun
from pokequant.domain.enums import RunStatus


class ProviderRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, provider: str, run_type: str) -> ProviderRun:
        run = ProviderRun(provider=provider, run_type=run_type, status=RunStatus.SUCCESS)
        self.session.add(run)
        self.session.flush()  # assign id
        return run

    def finish(
        self,
        run: ProviderRun,
        *,
        status: RunStatus,
        records_written: int = 0,
        request_count: int = 0,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        run.status = status
        run.finished_at = utcnow()
        run.records_written = records_written
        run.request_count = request_count
        run.message = message
        run.details = details or {}
        self.session.add(run)
