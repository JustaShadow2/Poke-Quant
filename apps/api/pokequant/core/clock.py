"""Time helpers. Always timezone-aware UTC; centralised so tests can patch it."""

from __future__ import annotations

from datetime import date, datetime, timezone


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(tz=timezone.utc)


def today() -> date:
    """Current UTC calendar date."""
    return utcnow().date()
