"""
HyperNexus VRL-1 — SecureRadialVault (Tier-1, in-memory).

Enrollment derives the static per-epoch coordinate and seals the routing
record with AEAD bound to (tenant, radius, shards, epoch, scopes).
Authentication re-derives the coordinate from the presented key, opens the
sealed record, and runs VRL1ZeroTrustEngine.verify_request. A shard
collision at enrollment is a hard panic — never a silent overwrite.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from core.transparency import MerkleLog
from core.vrl1_algo import Ring, VRL1ZeroTrustEngine, _canon
import struct


class ShardCollisionPanic(RuntimeError):
    """A 256-bit shard collision occurred. Statistically near-impossible:
    treat as an active attack / RNG failure, alert, refuse enrollment."""


class KeyOutOfRing(ValueError):
    """A bring-your-own key derived outside its tenant ring. Use generated
    keys (rejection-sampled into the ring) or reassign the ring."""


@dataclass
class _Sealed:
    tenant_id: str
    radius: int
    epoch: int
    scopes: list[str]
    blob: bytes


class SecureRadialVault:
    def __init__(self, engine: VRL1ZeroTrustEngine,
                 transparency: MerkleLog | None = None) -> None:
        self.engine = engine
        self.transparency = transparency if transparency is not None else MerkleLog()
        self._rings: dict[str, Ring] = {}
        self._by_shard: dict[tuple[int, int, int], _Sealed] = {}
        self._lock = threading.RLock()

    def transparency_root(self) -> str:
        return self.transparency.root()

    def register_tenant(self, tenant_id: str, ring: Ring) -> None:
        with self._lock:
            if tenant_id in self._rings:
                raise ValueError(f"tenant {tenant_id!r} already registered")
            for other_id, other in self._rings.items():
                if ring.overlaps(other):
                    raise ValueError(f"ring overlaps tenant {other_id!r}")
            self._rings[tenant_id] = ring

    def enroll_key(self, tenant_id: str, api_key: str, epoch: int,
                   target_url: str, db_connection_string: str,
                   scopes: list[str] | None = None) -> dict:
        scopes = scopes or ["*"]
        ring = self._rings[tenant_id]
        radius, shards = self.engine.derive_coordinate(tenant_id, api_key, epoch)
        if not ring.contains(radius):
            raise KeyOutOfRing(
                f"key derives to radius outside ring for {tenant_id!r}; "
                "use enroll_generated_key() or widen the ring")
        with self._lock:
            if shards in self._by_shard:
                raise ShardCollisionPanic(f"shard collision enrolling {tenant_id!r}")
            blob = self.engine.seal_record(
                tenant_id, radius, shards, epoch, scopes,
                {"target_url": target_url.rstrip("/"),
                 "db_connection_string": db_connection_string})
            self._by_shard[shards] = _Sealed(tenant_id, radius, epoch, scopes, blob)
            self.transparency.append(_canon(
                tenant_id.encode(), struct.pack(">Q", radius),
                struct.pack(">3Q", *shards), struct.pack(">q", epoch)))
        return {"tenant_id": tenant_id, "radius": radius, "shards": shards, "epoch": epoch}

    def enroll_generated_key(self, tenant_id: str, epoch: int, target_url: str,
                             db_connection_string: str,
                             scopes: list[str] | None = None,
                             max_tries: int = 10_000) -> tuple[str, dict]:
        """Generate CSPRNG keys until one derives in-ring (rejection sampling)."""
        for _ in range(max_tries):
            key = self.engine.generate_api_key()
            try:
                info = self.enroll_key(tenant_id, key, epoch,
                                       target_url, db_connection_string, scopes)
                return key, info
            except KeyOutOfRing:
                continue
        raise RuntimeError("no in-ring key found; ring is too narrow for rejection sampling")

    def authenticate(self, *, tenant_id: str, api_key: str, epoch: int,
                     current_epoch: int, nonce: str, ts: int, method: str,
                     path: str, body: bytes, proof: str,
                     now: float | None = None) -> dict:
        """Verify a request end-to-end and return its decrypted routing record."""
        ring = self._rings[tenant_id]
        # Dual-read: current epoch, then previous during rotation window.
        sealed = None
        for ep in (epoch, epoch - 1):
            _, shards = self.engine.derive_coordinate(tenant_id, api_key, ep)
            with self._lock:
                candidate = self._by_shard.get(shards)
            if candidate is not None:
                sealed, target_shards = candidate, shards
                break
        if sealed is None:
            raise PermissionError("unmapped shard")
        record = self.engine.open_record(tenant_id, sealed.radius, target_shards,
                                         sealed.epoch, sealed.scopes, sealed.blob)
        ok = self.engine.verify_request(
            tenant_id=tenant_id, api_key=api_key, epoch=sealed.epoch,
            current_epoch=current_epoch, ring=ring, target_shards=target_shards,
            nonce=nonce, ts=ts, method=method, path=path, body=body,
            proof=proof, now=now)
        if not ok:
            raise PermissionError("VRL-1 verification failed")
        return {"tenant_id": tenant_id, "scopes": sealed.scopes, **record}
