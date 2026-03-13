"""
Basic rate limiting — SPEC §11.

In-memory token bucket per tenant. Simple but effective for v0.1.
Production: swap with Redis-backed limiter.
"""

import time
import uuid
from collections import defaultdict

from malin.app.errors import RateLimitedError

# Per-tenant: max requests per window
_DEFAULT_MAX_REQUESTS = 30
_DEFAULT_WINDOW_SECONDS = 60

_buckets: dict[uuid.UUID, list[float]] = defaultdict(list)


def check_rate_limit(
    tenant_id: uuid.UUID,
    max_requests: int = _DEFAULT_MAX_REQUESTS,
    window_seconds: int = _DEFAULT_WINDOW_SECONDS,
) -> None:
    """Raise RateLimitedError if tenant exceeds rate limit on processing endpoints."""
    now = time.monotonic()
    timestamps = _buckets[tenant_id]

    # Purge expired entries
    _buckets[tenant_id] = [t for t in timestamps if now - t < window_seconds]
    timestamps = _buckets[tenant_id]

    if len(timestamps) >= max_requests:
        raise RateLimitedError()

    timestamps.append(now)
