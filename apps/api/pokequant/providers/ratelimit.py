"""Token-bucket rate limiting for provider calls.

Providers publish tight rate limits (docs/02-data-sources.md). A token bucket
gives smooth pacing with small bursts. The clock and sleep functions are
injectable so the limiter is deterministically testable without real waiting.
"""

from __future__ import annotations

import threading
import time
from typing import Callable


class TokenBucket:
    def __init__(
        self,
        rate_per_sec: float,
        capacity: float,
        *,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be > 0")
        self.rate = rate_per_sec
        self.capacity = capacity
        self._time = time_fn
        self._sleep = sleep_fn
        self._tokens = capacity
        self._updated = time_fn()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self._time()
        elapsed = now - self._updated
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._updated = now

    def acquire(self, tokens: float = 1.0) -> float:
        """Acquire `tokens`, sleeping if necessary. Returns seconds waited."""
        with self._lock:
            self._refill()
            waited = 0.0
            if self._tokens < tokens:
                deficit = tokens - self._tokens
                wait = deficit / self.rate
                self._sleep(wait)
                waited = wait
                self._refill()
            self._tokens -= tokens
            return waited


class RateLimiterRegistry:
    """Named token buckets, one per provider."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def register(self, name: str, rate_per_sec: float, capacity: float) -> TokenBucket:
        bucket = TokenBucket(rate_per_sec, capacity)
        self._buckets[name] = bucket
        return bucket

    def acquire(self, name: str, tokens: float = 1.0) -> float:
        bucket = self._buckets.get(name)
        if bucket is None:
            return 0.0
        return bucket.acquire(tokens)
