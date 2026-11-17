"""
HyperNexus VRL-1 — Radial Vector Engine (Proofs I–III).

Proof I  Spatilization: SHA-256(api_key) -> polar vector (r, theta_1..theta_{d-1}).
         First 64 bits -> radius fraction; remaining 192 bits -> angles in [0, 2*pi).
Proof II Boundary: a tenant owns ring [r_min, r_max); rings are disjoint, so a
         query radius outside the ring is rejected before any I/O.
Proof III Routing: radial gate (1 subtraction) + angular match in O(d) time,
         d fixed => O(1) in the number of tenants N. No table scan.

Honest scope: this is a deterministic geometric *index + gate* in software.
It drops cross-ring requests at the math layer (before HTTP/DB), which is
defense-in-depth on top of — not a replacement for — auth and encryption.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from core import _rust

TWO_PI = 2.0 * np.pi
_MAX_UINT64 = float(2**64 - 1)


@dataclass(frozen=True)
class RadialVector:
    radius: float
    angles: np.ndarray  # shape (d-1,), each in [0, 2*pi)


class RadialVectorEngine:
    """Converts API keys to polar coordinates and verifies ring membership."""

    def __init__(self, dimensions: int = 4, ring_width: float = 100.0) -> None:
        if not 2 <= dimensions <= 9:
            raise ValueError("dimensions must be in [2, 9] (192 payload bits / 24-bit min chunk)")
        if ring_width <= 0:
            raise ValueError("ring_width must be positive")
        self.dimensions = dimensions
        self.ring_width = float(ring_width)

    # -- Proof I ---------------------------------------------------------
    def spatialize_key(self, api_key: str) -> tuple[float, np.ndarray]:
        """Map `api_key` to (radius, angles). Deterministic; same key, same vector."""
        if not api_key:
            raise ValueError("api_key must be non-empty")
        # Rust path covers the locked/default d=4, ring_width=100 case.
        if _rust.RUST_AVAILABLE and self.dimensions == 4 and self.ring_width == 100.0:
            radius, angles = _rust.rust_spatialize_key(api_key)
            return radius, np.asarray(angles, dtype=np.float64)
        digest = hashlib.sha256(api_key.encode("utf-8")).digest()  # 32 bytes
        frac = int.from_bytes(digest[:8], "big") / _MAX_UINT64     # [0, 1]
        radius = self.ring_width * (1.0 + frac)                    # [W, 2W)
        payload = digest[8:32]                                     # 24 bytes = 192 bits
        n_angles = self.dimensions - 1
        chunk = len(payload) // n_angles
        angles = np.empty(n_angles, dtype=np.float64)
        denom = float(2 ** (chunk * 8) - 1)
        for i in range(n_angles):
            seg = payload[i * chunk:(i + 1) * chunk]
            angles[i] = TWO_PI * (int.from_bytes(seg, "big") / denom)
        return radius, angles

    def radial_fraction(self, api_key: str) -> float:
        """Radius as a fraction in [0, 1) — used to project into any tenant ring."""
        digest = hashlib.sha256(api_key.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / _MAX_UINT64

    @staticmethod
    def project_radius(fraction: float, r_min: float, r_max: float) -> float:
        """Project a [0,1) fraction into ring [r_min, r_max). Keeps rings disjoint."""
        if not r_min < r_max:
            raise ValueError("require r_min < r_max")
        return r_min + fraction * (r_max - r_min)

    # -- Proof III helpers -------------------------------------------------
    @staticmethod
    def angular_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Shortest wrap-around angular distance per axis, in [0, pi]."""
        diff = np.abs(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64))
        return np.minimum(diff, TWO_PI - diff)

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity of Cartesian embeddings of equal-radius polar points.

        For points on the same ring, cos-similarity is a monotone proxy for
        angular closeness; the per-axis angular gate below is the strict check.
        """
        ca, cb = np.cos(a), np.cos(b)
        sa, sb = np.sin(a), np.sin(b)
        va = np.concatenate([ca, sa])
        vb = np.concatenate([cb, sb])
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        return float(np.dot(va, vb) / denom) if denom else 0.0

    # -- Proofs II + III ---------------------------------------------------
    def route_payload(
        self,
        query_r: float,
        query_angles: np.ndarray,
        tenant_min_r: float,
        tenant_max_r: float,
        target_angles: np.ndarray,
        tolerance: float = 1e-9,
    ) -> bool:
        """True iff radius is inside [tenant_min_r, tenant_max_r) AND every
        angular axis matches within `tolerance`. Constant time in N."""
        # Phase 1 — radial gate: one comparison chain, no I/O on failure.
        if not (tenant_min_r <= query_r < tenant_max_r):
            return False
        # Phase 2 — angular match: O(d), d fixed.
        q = np.asarray(query_angles, dtype=np.float64)
        t = np.asarray(target_angles, dtype=np.float64)
        if q.shape != t.shape:
            return False
        return bool(np.all(self.angular_distance(q, t) < tolerance))
