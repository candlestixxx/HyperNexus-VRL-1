"""
HyperNexus VRL-1 — RadialVault (in-memory testing vault).

Tenants register a disjoint ring [r_min, r_max). Endpoints are indexed by
their quantized angular coordinate (the spatial shard), never by scanning
tenants. Resolution re-spatializes the presented key, projects its radius
into the candidate tenant's ring, and lets RadialVectorEngine.route_payload
decide. Cross-ring / unknown keys raise RadialVaultUnauthorized before any
HTTP or DB work happens.
"""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass

import numpy as np

from core.vector_math import RadialVectorEngine


class RadialVaultUnauthorized(PermissionError):
    """Raised when a key fails the radial gate or angular match."""


@dataclass
class _Tenant:
    tenant_id: str
    r_min: float
    r_max: float


@dataclass
class _Endpoint:
    tenant_id: str
    radius: float  # projected into the tenant ring at store time
    angles: np.ndarray
    target_url: str
    db_connection_string: str


class RadialVault:
    def __init__(self, engine: RadialVectorEngine | None = None) -> None:
        self.engine = engine or RadialVectorEngine()
        self._tenants: dict[str, _Tenant] = {}
        # Spatial index: quantized angle tuple -> endpoint. O(1) dict lookup.
        self._by_shard: dict[tuple[float, ...], _Endpoint] = {}
        self._lock = threading.RLock()

    # -- tenants ---------------------------------------------------------
    def register_tenant(self, tenant_id: str, min_r: float, max_r: float) -> None:
        if not tenant_id:
            raise ValueError("tenant_id must be non-empty")
        if not min_r < max_r:
            raise ValueError("require min_r < max_r")
        with self._lock:
            if tenant_id in self._tenants:
                raise ValueError(f"tenant {tenant_id!r} already registered")
            for t in self._tenants.values():  # rings must be disjoint (Proof II)
                if min_r < t.r_max and t.r_min < max_r:
                    raise ValueError(
                        f"ring [{min_r}, {max_r}) overlaps tenant {t.tenant_id!r} "
                        f"[{t.r_min}, {t.r_max})"
                    )
            self._tenants[tenant_id] = _Tenant(tenant_id, float(min_r), float(max_r))

    # -- endpoints ---------------------------------------------------------
    @staticmethod
    def _shard(angles: np.ndarray) -> tuple[float, ...]:
        # Quantize to 1e-12 rad: stable dict key, far above float64 noise here.
        return tuple(np.round(np.asarray(angles, dtype=np.float64), 12).tolist())

    def store_endpoint(
        self,
        api_key: str,
        target_url: str,
        db_connection_string: str,
        tenant_id: str | None = None,
    ) -> dict:
        """Spatialize `api_key` and store its endpoint under its angular shard."""
        _, angles = self.engine.spatialize_key(api_key)
        frac = self.engine.radial_fraction(api_key)
        with self._lock:
            tenant = self._pick_tenant(tenant_id, frac)
            radius = self.engine.project_radius(frac, tenant.r_min, tenant.r_max)
            ep = _Endpoint(tenant.tenant_id, radius, angles.copy(),
                           target_url.rstrip("/"), db_connection_string)
            self._by_shard[self._shard(angles)] = ep
            return {"tenant_id": tenant.tenant_id, "radius": radius,
                    "angles": angles.tolist(), "target_url": ep.target_url}

    def _pick_tenant(self, tenant_id: str | None, frac: float) -> _Tenant:
        if tenant_id is not None:
            t = self._tenants.get(tenant_id)
            if t is None:
                raise ValueError(f"unknown tenant {tenant_id!r}")
            return t
        # Infer: the tenant whose ring contains the raw spatialized radius.
        raw_r = self.engine.ring_width * (1.0 + frac)
        for t in self._tenants.values():
            if t.r_min <= raw_r < t.r_max:
                return t
        raise ValueError("no registered ring contains this key's radius; pass tenant_id")

    def resolve_endpoint(self, api_key: str) -> dict:
        """Verify `api_key` geometrically and return its routing target.

        Raises RadialVaultUnauthorized on unknown shard or failed gate —
        callers must not fall back to any legacy password check.
        """
        _, angles = self.engine.spatialize_key(api_key)
        frac = self.engine.radial_fraction(api_key)
        with self._lock:
            ep = self._by_shard.get(self._shard(angles))
            if ep is None:
                raise RadialVaultUnauthorized("unmapped angular shard")
            tenant = self._tenants[ep.tenant_id]
            query_r = self.engine.project_radius(frac, tenant.r_min, tenant.r_max)
            ok = self.engine.route_payload(
                query_r, angles, tenant.r_min, tenant.r_max, ep.angles)
            if not ok:
                raise RadialVaultUnauthorized("radial/angular gate rejected key")
            return {
                "tenant_id": ep.tenant_id,
                "target_url": ep.target_url,
                "db_connection_string": ep.db_connection_string,
                "radius": query_r,
                "angles": angles.tolist(),
                # Fingerprint for logs only — never log the raw key.
                "key_fingerprint": hashlib.sha256(api_key.encode()).hexdigest()[:12],
            }

    def list_tenants(self) -> list[dict]:
        with self._lock:
            return [{"tenant_id": t.tenant_id, "r_min": t.r_min, "r_max": t.r_max}
                    for t in self._tenants.values()]
