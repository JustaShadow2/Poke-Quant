"""UUIDv7 generation (RFC 9562).

Time-ordered UUIDs give us globally-unique, index-friendly primary keys whose
natural sort order is (roughly) creation order - better locality than uuid4 for
B-tree indexes (docs/03-database-design.md - Design principles).
"""

from __future__ import annotations

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    """Return a new UUIDv7 (48-bit ms timestamp + 74 random bits)."""
    ms = time.time_ns() // 1_000_000
    rand = os.urandom(10)
    b = bytearray(16)
    b[0] = (ms >> 40) & 0xFF
    b[1] = (ms >> 32) & 0xFF
    b[2] = (ms >> 24) & 0xFF
    b[3] = (ms >> 16) & 0xFF
    b[4] = (ms >> 8) & 0xFF
    b[5] = ms & 0xFF
    b[6] = 0x70 | (rand[0] & 0x0F)  # version 7
    b[7] = rand[1]
    b[8] = 0x80 | (rand[2] & 0x3F)  # RFC 4122 variant
    b[9] = rand[3]
    b[10:16] = rand[4:10]
    return uuid.UUID(bytes=bytes(b))
