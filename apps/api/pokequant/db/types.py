"""Reusable column type helpers shared by models and migrations."""

from __future__ import annotations

from enum import Enum

import sqlalchemy as sa


def pg_enum(py_enum: type[Enum], name: str) -> sa.Enum:
    """A portable VARCHAR+CHECK enum that stores the enum *value* (not its name).

    Using ``native_enum=False`` avoids Postgres native ENUM types, which are
    painful to alter in migrations. ``values_callable`` ensures we persist the
    lowercase string values (e.g. "success"), matching our JSON/API contracts.
    """
    return sa.Enum(
        py_enum,
        name=name,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
    )


# Money: fixed-precision to avoid float rounding on prices.
Money = sa.Numeric(14, 2)
