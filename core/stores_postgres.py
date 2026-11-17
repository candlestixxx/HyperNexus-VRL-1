"""PostgreSQL shared stores for the nonce + capability-usage interfaces.

Implements the same duck-typed protocols as the in-memory, SQLite, and Redis
backends, so any is drop-in for `VRL1ZeroTrustEngine(nonce_store=...)` and
`SecureRadialVault(usage_store=...)`. Atomicity comes from Postgres:

- nonce replay check -> `INSERT ... ON CONFLICT (tenant_id, nonce) DO NOTHING`
  (rowcount 1 = first insert, 0 = replay), with an `expires_at` column pruned
  on each call;
- capability budget  -> `INSERT ... ON CONFLICT (jti) DO UPDATE SET used =
  used + 1 RETURNING used` (single atomic statement).

`psycopg` is imported lazily so the rest of the package works without it.
Tests run against a real local Postgres via `embedded-postgres`.
"""
from __future__ import annotations

import threading
import time


class PostgresNonceStore:
    """Tenant-scoped, expiring replay ledger backed by PostgreSQL."""

    def __init__(self, dsn: str, ttl_seconds: int = 300, conn=None) -> None:
        self.ttl = ttl_seconds
        if conn is not None:
            self._conn = conn
        else:
            import psycopg
            self._conn = psycopg.connect(dsn)
        self._lock = threading.Lock()
        with self._conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS nonces ("
                " tenant_id TEXT NOT NULL,"
                " nonce TEXT NOT NULL,"
                " expires_at DOUBLE PRECISION NOT NULL,"
                " PRIMARY KEY (tenant_id, nonce))")
        self._conn.commit()

    def check_and_record(self, tenant_id: str, nonce: str,
                         now: float | None = None) -> bool:
        now = time.time() if now is None else now
        expires = now + self.ttl
        with self._lock:
            with self._conn.cursor() as cur:
                # Opportunistic prune of expired nonces (bounded table growth).
                cur.execute("DELETE FROM nonces WHERE expires_at <= %s", (now,))
                # Atomic first-insert wins: rowcount 1 = inserted, 0 = replay.
                cur.execute(
                    "INSERT INTO nonces (tenant_id, nonce, expires_at) "
                    "VALUES (%s, %s, %s) "
                    "ON CONFLICT (tenant_id, nonce) DO NOTHING",
                    (tenant_id, nonce, expires))
                inserted = cur.rowcount == 1
            self._conn.commit()
            return inserted

    def close(self) -> None:
        self._conn.close()


class PostgresCapabilityUsageStore:
    """max_uses accounting backed by PostgreSQL (atomic upsert increment)."""

    def __init__(self, dsn: str, conn=None) -> None:
        if conn is not None:
            self._conn = conn
        else:
            import psycopg
            self._conn = psycopg.connect(dsn)
        self._lock = threading.Lock()
        with self._conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS cap_usage ("
                " jti TEXT PRIMARY KEY,"
                " used INTEGER NOT NULL)")
        self._conn.commit()

    def try_use(self, jti: str, max_uses: int) -> bool:
        if max_uses <= 0:
            return True  # unlimited
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO cap_usage (jti, used) VALUES (%s, 1) "
                    "ON CONFLICT (jti) DO UPDATE SET used = cap_usage.used + 1 "
                    "RETURNING used", (jti,))
                used = cur.fetchone()[0]
            self._conn.commit()
            return used <= max_uses

    def close(self) -> None:
        self._conn.close()
