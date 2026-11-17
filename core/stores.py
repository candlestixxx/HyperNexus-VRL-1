"""Shared-store backends behind the nonce + capability-usage interfaces.

The engine and vault consume these via duck-typed protocols, so the in-memory
implementations (core.vrl1_algo.NonceLedger, core.capability.CapabilityUsageLedger)
and these SQLite backends are interchangeable. SQLite (WAL) is the verifiable,
in-repo shared store: it works across threads and processes without an external
service. Redis/Postgres drivers can implement the same protocols for horizontal
scale (ROADMAP Milestone 4) without touching the call sites.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Protocol


class NonceStore(Protocol):
    """Atomic replay check: True if recorded now, False if already seen."""

    def check_and_record(self, tenant_id: str, nonce: str,
                         now: float | None = None) -> bool: ...


class CapabilityUsageStore(Protocol):
    """Atomic use-budget check for capability tokens (max_uses)."""

    def try_use(self, jti: str, max_uses: int) -> bool: ...


class SQLiteNonceStore:
    """Tenant-scoped, expiring replay ledger backed by SQLite (WAL)."""

    def __init__(self, path: str, ttl_seconds: int = 300) -> None:
        self.ttl = ttl_seconds
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS nonces ("
            " tenant_id TEXT NOT NULL,"
            " nonce TEXT NOT NULL,"
            " expires_at REAL NOT NULL,"
            " PRIMARY KEY (tenant_id, nonce))")
        self._conn.commit()
        self._lock = threading.Lock()

    def check_and_record(self, tenant_id: str, nonce: str,
                         now: float | None = None) -> bool:
        now = time.time() if now is None else now
        expires = now + self.ttl
        with self._lock:
            try:
                # Opportunistic prune of expired nonces (bounded table growth).
                self._conn.execute("DELETE FROM nonces WHERE expires_at <= ?", (now,))
                self._conn.execute(
                    "INSERT INTO nonces (tenant_id, nonce, expires_at) VALUES (?, ?, ?)",
                    (tenant_id, nonce, expires))
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                # PRIMARY KEY conflict => replay. End the failed transaction.
                self._conn.rollback()
                return False

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class SQLiteCapabilityUsageStore:
    """max_uses accounting backed by SQLite (WAL); shared across instances."""

    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cap_usage ("
            " jti TEXT PRIMARY KEY,"
            " used INTEGER NOT NULL)")
        self._conn.commit()
        self._lock = threading.Lock()

    def try_use(self, jti: str, max_uses: int) -> bool:
        if max_uses <= 0:
            return True  # unlimited
        with self._lock:
            # Single atomic increment; fail-closed once the budget is exceeded.
            self._conn.execute(
                "INSERT INTO cap_usage (jti, used) VALUES (?, 1) "
                "ON CONFLICT(jti) DO UPDATE SET used = cap_usage.used + 1", (jti,))
            self._conn.commit()
            row = self._conn.execute(
                "SELECT used FROM cap_usage WHERE jti = ?", (jti,)).fetchone()
            return bool(row) and row[0] <= max_uses

    def close(self) -> None:
        with self._lock:
            self._conn.close()
