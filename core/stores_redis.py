"""Redis-backed shared stores for the nonce + capability-usage interfaces.

Implements the same duck-typed protocols as the in-memory and SQLite backends
(`core/stores.py`), so any of them is drop-in for `VRL1ZeroTrustEngine(nonce_store=...)`
and `SecureRadialVault(usage_store=...)`. Atomicity comes from Redis primitives:

- nonce replay check  -> `SET key 1 NX EX ttl` (atomic first-insert wins);
- capability budget   -> `INCR key` (atomic increment), compared to max_uses.

The `redis` package is imported lazily so the rest of the package works
without it. Tests run against `fakeredis` (no server); production points at a
real Redis via `url` or an injected client.
"""
from __future__ import annotations

import time


class RedisNonceStore:
    """Tenant-scoped, expiring replay ledger backed by Redis."""

    def __init__(self, url: str = "redis://localhost:6379/0", ttl_seconds: int = 300,
                 client=None) -> None:
        self.ttl = ttl_seconds
        if client is not None:
            self._client = client
        else:
            import redis as _redis
            self._client = _redis.Redis.from_url(url)

    def check_and_record(self, tenant_id: str, nonce: str,
                         now: float | None = None) -> bool:
        key = f"vrl1:nonce:{tenant_id}:{nonce}"
        # SET NX EX is atomic: truthy only when this call inserted the key,
        # i.e. the nonce was not already seen. Expiry prunes the table for us.
        return bool(self._client.set(key, "1", nx=True, ex=self.ttl))

    def close(self) -> None:
        self._client.close()


class RedisCapabilityUsageStore:
    """max_uses accounting backed by Redis (atomic INCR)."""

    def __init__(self, url: str = "redis://localhost:6379/0", client=None) -> None:
        if client is not None:
            self._client = client
        else:
            import redis as _redis
            self._client = _redis.Redis.from_url(url)

    def try_use(self, jti: str, max_uses: int) -> bool:
        if max_uses <= 0:
            return True  # unlimited
        key = f"vrl1:cap:{jti}"
        used = self._client.incr(key)  # atomic increment, fail-closed past budget
        return used <= max_uses

    def close(self) -> None:
        self._client.close()
