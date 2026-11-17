"""
HyperNexus VRL-1 — SecureRadialVault (Tier-1, in-memory).

Enrollment derives the static per-epoch coordinate and seals the routing
record with AEAD bound to (tenant, radius, shards, epoch, scopes).
Authentication re-derives the coordinate from the presented key, opens the
sealed record, and runs VRL1ZeroTrustEngine.verify_request. A shard
collision at enrollment is a hard panic — never a silent overwrite.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
from dataclasses import dataclass

from core.capability import CapabilityError, CapabilityUsageLedger, scopes_satisfied
from core.capability import mint as _mint_capability
from core.capability import parse_and_verify as _parse_capability
from core.security_monitor import CUSUMAnomalyDetector
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
    shards: tuple[int, int, int]


class SecureRadialVault:
    def __init__(self, engine: VRL1ZeroTrustEngine,
                 transparency: MerkleLog | None = None,
                 persistence_path: str | None = None,
                 monitor: CUSUMAnomalyDetector | None = None) -> None:
        self.engine = engine
        self.transparency = transparency if transparency is not None else MerkleLog()
        self.persistence_path = persistence_path
        self._monitor = monitor if monitor is not None else CUSUMAnomalyDetector()
        self._rings: dict[str, Ring] = {}
        self._by_shard: dict[tuple[int, int, int], _Sealed] = {}
        # tenant_id -> enrolled shards (capability minting target resolution)
        self._tenant_shards: dict[str, set[tuple[int, int, int]]] = {}
        self._usage = CapabilityUsageLedger()
        self._lock = threading.RLock()
        if persistence_path:
            self._load()

    def transparency_root(self) -> str:
        return self.transparency.root()

    def transparency_signature(self) -> str:
        return self.engine.sign_root(self.transparency.root())

    # -- persistence: sealed AEAD blobs + rings + log leaves, atomically -------
    def _save(self) -> None:
        if not self.persistence_path:
            return
        data = {
            "rings": {tid: [r.r_min, r.r_max] for tid, r in self._rings.items()},
            "records": [{
                "tenant_id": s.tenant_id, "radius": s.radius, "epoch": s.epoch,
                "scopes": s.scopes, "shards": list(shards),
                "blob": base64.b64encode(s.blob).decode(),
            } for shards, s in self._by_shard.items()],
            "transparency_leaves": self.transparency.export_state(),
            "transparency_root": self.transparency.root(),
            "transparency_signature": self.transparency_signature(),
        }
        tmp = self.persistence_path + ".tmp"
        os.makedirs(os.path.dirname(os.path.abspath(self.persistence_path)), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, self.persistence_path)

    def _load(self) -> None:
        if not os.path.exists(self.persistence_path):
            return
        with open(self.persistence_path, encoding="utf-8") as f:
            data = json.load(f)
        # Refuse a rolled-back/forged state file: signature must verify.
        if not self.engine.verify_root_signature(
                data["transparency_root"], data["transparency_signature"]):
            raise ValueError("vault persistence failed transparency signature check")
        self.transparency.load_state(data.get("transparency_leaves", []))
        if self.transparency.root() != data["transparency_root"]:
            raise ValueError("vault persistence transparency root mismatch")
        for tid, (lo, hi) in data.get("rings", {}).items():
            self._rings[tid] = Ring(lo, hi)
        for rec in data.get("records", []):
            shards = tuple(rec["shards"])
            self._by_shard[shards] = _Sealed(
                rec["tenant_id"], rec["radius"], rec["epoch"], rec["scopes"],
                base64.b64decode(rec["blob"]), shards)
        # Rebuild the tenant->shards index from loaded records.
        for shards, sealed in self._by_shard.items():
            self._tenant_shards.setdefault(sealed.tenant_id, set()).add(shards)

    def has_tenant(self, tenant_id: str) -> bool:
        return tenant_id in self._rings

    def register_tenant(self, tenant_id: str, ring: Ring) -> None:
        with self._lock:
            if tenant_id in self._rings:
                raise ValueError(f"tenant {tenant_id!r} already registered")
            for other_id, other in self._rings.items():
                if ring.overlaps(other):
                    raise ValueError(f"ring overlaps tenant {other_id!r}")
            self._rings[tenant_id] = ring
            self._tenant_shards.setdefault(tenant_id, set())
            self._save()

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
            self._by_shard[shards] = _Sealed(tenant_id, radius, epoch, scopes, blob, shards)
            self._tenant_shards.setdefault(tenant_id, set()).add(shards)
            self.transparency.append(_canon(
                tenant_id.encode(), struct.pack(">Q", radius),
                struct.pack(">3Q", *shards), struct.pack(">q", epoch)))
            self._save()
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

    def open_circuits(self) -> dict[str, float]:
        """Currently-open circuit-breaker keys -> cooldown seconds remaining."""
        return self._monitor.open_circuits()

    def authenticate(self, *, tenant_id: str, api_key: str, epoch: int,
                     current_epoch: int, nonce: str, ts: int, method: str,
                     path: str, body: bytes, proof: str,
                     now: float | None = None) -> dict:
        """Verify a request end-to-end and return its decrypted routing record.

        A CUSUM circuit breaker gates the tenant and the derived shard: while
        open, the request is rejected before the proof/nonce machinery, so a
        flood is shed cheaply and never burns the victim's nonce ledger."""
        ring = self._rings.get(tenant_id)
        if ring is None:
            raise PermissionError("unknown tenant")
        tkey = f"tenant:{tenant_id}"
        if self._monitor.is_open(tkey, now):
            raise PermissionError("circuit breaker open (tenant)")
        # Dual-read: current epoch, then previous during rotation window.
        sealed = None
        target_shards = None
        for ep in (epoch, epoch - 1):
            _, shards = self.engine.derive_coordinate(tenant_id, api_key, ep)
            with self._lock:
                candidate = self._by_shard.get(shards)
            if candidate is not None:
                sealed, target_shards = candidate, shards
                break
        key_shards = target_shards if target_shards is not None else shards
        skey = f"shard:{tenant_id}:{key_shards[0]}:{key_shards[1]}:{key_shards[2]}"
        if self._monitor.is_open(skey, now):
            raise PermissionError("circuit breaker open (shard)")

        def _fail(reason: str):
            self._monitor.record_failure(tkey, now)
            self._monitor.record_failure(skey, now)
            raise PermissionError(reason)

        if sealed is None:
            _fail("unmapped shard")
        try:
            record = self.engine.open_record(tenant_id, sealed.radius, target_shards,
                                             sealed.epoch, sealed.scopes, sealed.blob)
        except Exception:
            _fail("record failed AEAD authentication")
        ok = self.engine.verify_request(
            tenant_id=tenant_id, api_key=api_key, epoch=sealed.epoch,
            current_epoch=current_epoch, ring=ring, target_shards=target_shards,
            nonce=nonce, ts=ts, method=method, path=path, body=body,
            proof=proof, now=now)
        if not ok:
            _fail("VRL-1 verification failed")
        self._monitor.record_success(tkey, now)
        self._monitor.record_success(skey, now)
        return {"tenant_id": tenant_id, "scopes": sealed.scopes, **record}

    # -- capability-attenuated agent tokens -----------------------------------
    def mint_agent_token(self, tenant_id: str, *, scopes: list[str], exp: int,
                         path_prefix: str = "", max_uses: int = 0,
                         now: int | None = None) -> str:
        """Mint a signed, caveated agent token against the tenant's latest
        (highest-epoch) enrollment. The raw API key is never required here:
        the admin resolves the credential by tenant + epoch."""
        now = int(time.time()) if now is None else now
        with self._lock:
            if tenant_id not in self._rings:
                raise ValueError(f"unknown tenant {tenant_id!r}")
            shards = self._latest_shards(tenant_id)
            if shards is None:
                raise ValueError(f"tenant {tenant_id!r} has no enrolled credential")
            sealed = self._by_shard[shards]
            if not scopes_satisfied(set(scopes), set(sealed.scopes)):
                raise ValueError(
                    f"capability scopes {sorted(scopes)} exceed enrolled "
                    f"scopes {sorted(sealed.scopes)}")
        return _mint_capability(self.engine, tenant_id=tenant_id, shards=shards,
                               scopes=scopes, exp=exp, path_prefix=path_prefix,
                               max_uses=max_uses, now=now)

    def authenticate_agent_token(self, token: str, *, method: str, path: str,
                                 now: float | None = None) -> dict:
        """Verify a capability token and return its routing record with the
        attenuated scopes. Raises PermissionError on any failure so callers map
        every failure to 403 with no upstream side effects."""
        now_f = time.time() if now is None else now
        try:
            cap = _parse_capability(self.engine, token, now=int(now_f))
        except CapabilityError as e:
            raise PermissionError(str(e))
        # Caveat: path prefix (empty = unrestricted).
        if cap.path_prefix and not path.startswith(cap.path_prefix):
            raise PermissionError("capability path prefix mismatch")
        with self._lock:
            sealed = self._by_shard.get(cap.shards)
        if sealed is None or sealed.tenant_id != cap.tenant_id:
            raise PermissionError("unmapped capability shard")
        if not scopes_satisfied(set(cap.scopes), set(sealed.scopes)):
            raise PermissionError("capability scope escalation")
        # Open the AEAD record (fails InvalidTag if moved/tampered).
        try:
            record = self.engine.open_record(
                cap.tenant_id, sealed.radius, cap.shards, sealed.epoch,
                sealed.scopes, sealed.blob)
        except Exception:
            raise PermissionError("capability record failed AEAD authentication")
        # Caveat: max-use budget, consumed only after every other check passed.
        if not self._usage.try_use(cap.jti, cap.max_uses):
            raise PermissionError("capability use budget exhausted")
        return {"tenant_id": cap.tenant_id, "scopes": cap.scopes, **record}

    def _latest_shards(self, tenant_id: str) -> tuple[int, int, int] | None:
        """Highest-epoch enrolled shard tuple for a tenant, or None."""
        best_shards = None
        best_epoch = -1
        for shards in self._tenant_shards.get(tenant_id, set()):
            sealed = self._by_shard.get(shards)
            if sealed is not None and sealed.epoch > best_epoch:
                best_shards, best_epoch = shards, sealed.epoch
        return best_shards
