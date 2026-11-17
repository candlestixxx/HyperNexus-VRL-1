"""CUSUM anomaly detection + circuit breaker (fail-closed brute-force defense).

The vault feeds auth failures/successes into this monitor, keyed by both the
tenant (`tenant:<id>`) and the derived shard (`shard:<id>:<s0>:<s1>:<s2>`).
A CUSUM control chart accumulates positive drift whenever the observed
failure rate exceeds a baseline; crossing a threshold opens a circuit for a
cooldown window. While open, the vault rejects the key *before* running the
proof/nonce machinery — so a flood is shed cheaply and, crucially, the
victim's nonce ledger is never burned by requests the breaker rejected.

This is runtime state only (not persisted). Shared-store backends are a
later milestone (ROADMAP Milestone 4); the interface is deliberately narrow
so a Redis/Postgres-backed monitor can be swapped in without touching the
vault call sites.
"""
from __future__ import annotations

import threading
import time


class CUSUMAnomalyDetector:
    def __init__(self, window_seconds: float = 10.0, baseline_rate: float = 0.5,
                 threshold: float = 8.0, cooldown_seconds: float = 30.0) -> None:
        self.window = window_seconds
        self.baseline = baseline_rate
        self.threshold = threshold
        self.cooldown = cooldown_seconds
        # key -> {"s": cumulative score, "fails": [timestamps], "tripped_at": float}
        self._state: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _prune(self, st: dict, now: float) -> None:
        st["fails"] = [t for t in st["fails"] if now - t < self.window]

    def record_failure(self, key: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            st = self._state.setdefault(key, {"s": 0.0, "fails": [], "tripped_at": 0.0})
            self._prune(st, now)
            st["fails"].append(now)
            rate = len(st["fails"]) / self.window
            # Positive drift only above baseline; below baseline we decay.
            st["s"] = max(0.0, st["s"] + (rate - self.baseline))
            if st["s"] >= self.threshold:
                st["tripped_at"] = now
                st["s"] = 0.0
                st["fails"] = []

    def record_success(self, key: str, now: float | None = None) -> None:
        """Legitimate traffic recovers the circuit (score + history + trip reset)."""
        with self._lock:
            st = self._state.get(key)
            if st is not None:
                st["s"] = 0.0
                st["fails"] = []
                st["tripped_at"] = 0.0

    def is_open(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            st = self._state.get(key)
            if st is None:
                return False
            if st["tripped_at"]:
                if now - st["tripped_at"] < self.cooldown:
                    return True
                # Cooldown elapsed: auto-close and reset.
                st["tripped_at"] = 0.0
                st["s"] = 0.0
                st["fails"] = []
            return False

    def open_circuits(self, now: float | None = None) -> dict[str, float]:
        """Currently-open keys -> seconds of cooldown remaining (observability)."""
        now = time.time() if now is None else now
        with self._lock:
            out: dict[str, float] = {}
            for key, st in self._state.items():
                if st["tripped_at"] and now - st["tripped_at"] < self.cooldown:
                    out[key] = round(self.cooldown - (now - st["tripped_at"]), 1)
            return out
