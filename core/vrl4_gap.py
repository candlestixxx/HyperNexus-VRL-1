"""HyperNexus VRL-4 — Geometric Authentication Protocol (GAP), Python layer.

Layers:
  1. Physics  — fuzzy-extracted device key (hardware entropy, never a password)
  2. Light    — RTT + Kalman latency sphere + WGS 84 geodesic distance bound
  3. Math     — VRL-1 exact integer-torus ring check (the existing engine)

The pure-math primitives have pure-Python fallbacks and are accelerated by the
`_vrl4_gap` Rust extension when it is installed. `GapAuthenticator` composes the
three layers on top of the existing VRL-1 engine/vault — the seam where GAP
(a separate product) hands a proven device to VRL-1 (the vault).
"""
from __future__ import annotations

import hashlib
import hmac
import math
import os
import secrets
import time
from dataclasses import dataclass, field

try:
    from _vrl4_gap import (fuzzy_generate as _rg_fuzzy_generate,
                           fuzzy_reproduce as _rg_fuzzy_reproduce,
                           sign_challenge as _rg_sign_challenge,
                           verify_challenge as _rg_verify_challenge,
                           haversine_km as _rg_haversine_km,
                           max_radius_km as _rg_max_radius_km,
                           KalmanTracker as _RustKalmanTracker)
    RUST_GAP = True
except Exception:  # pragma: no cover - import failure on platforms without the wheel
    RUST_GAP = False

_EARTH_RADIUS_KM = 6371.0
_KEY_LEN = 32  # 256-bit device key


# ---------------------------------------------------------------------------
# Pure-Python fallbacks (mirror the Rust primitives)
# ---------------------------------------------------------------------------
def _pack_bits(bits: list[int]) -> bytes:
    out = bytearray((len(bits) + 7) // 8)
    for j, bit in enumerate(bits):
        if bit:
            out[j // 8] |= 1 << (7 - (j % 8))
    return bytes(out)


def _unpack_bits(data: bytes) -> list[int]:
    bits = []
    for b in data:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits


def _py_fuzzy_generate(reading: bytes, key_len: int, repeat: int) -> tuple[bytes, bytes]:
    key = secrets.token_bytes(key_len)
    bits: list[int] = []
    for b in key:
        for i in range(7, -1, -1):
            bits.extend([(b >> i) & 1] * repeat)
    codeword = _pack_bits(bits)
    helper = bytes(c ^ r for c, r in zip(codeword, reading))
    return key, helper


def _py_fuzzy_reproduce(reading: bytes, helper: bytes, key_len: int, repeat: int) -> bytes:
    codeword = bytes(h ^ r for h, r in zip(helper, reading))
    bits = _unpack_bits(codeword)
    key_bits = []
    for start in range(0, key_len * 8 * repeat, repeat):
        ones = sum(bits[start:start + repeat])
        key_bits.append(1 if ones * 2 >= repeat else 0)
    return _pack_bits(key_bits)


def _py_sign_challenge(key: bytes, nonce: bytes, client_nonce: bytes, payload: bytes) -> bytes:
    return hmac.new(key, b"VRL4-GAP-v1" + nonce + client_nonce + payload, hashlib.sha256).digest()


def _py_verify_challenge(key: bytes, nonce: bytes, client_nonce: bytes, payload: bytes,
                         sig: bytes) -> bool:
    return hmac.compare_digest(_py_sign_challenge(key, nonce, client_nonce, payload), sig)


def _py_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _py_max_radius_km(rtt_ms: float, speed_km_per_ms: float) -> float:
    return rtt_ms * speed_km_per_ms / 2.0


# ---------------------------------------------------------------------------
# Public primitive API (Rust-accelerated when available)
# ---------------------------------------------------------------------------
def fuzzy_generate(reading: bytes, key_len: int = _KEY_LEN, repeat: int = 3) -> tuple[bytes, bytes]:
    if RUST_GAP:
        return _rg_fuzzy_generate(reading, key_len, repeat)
    return _py_fuzzy_generate(reading, key_len, repeat)


def fuzzy_reproduce(reading: bytes, helper: bytes, key_len: int = _KEY_LEN, repeat: int = 3) -> bytes:
    if RUST_GAP:
        return _rg_fuzzy_reproduce(reading, helper, key_len, repeat)
    return _py_fuzzy_reproduce(reading, helper, key_len, repeat)


def sign_challenge(key: bytes, nonce: bytes, client_nonce: bytes, payload: bytes) -> bytes:
    if RUST_GAP:
        return _rg_sign_challenge(key, nonce, client_nonce, payload)
    return _py_sign_challenge(key, nonce, client_nonce, payload)


def verify_challenge(key: bytes, nonce: bytes, client_nonce: bytes, payload: bytes,
                     sig: bytes) -> bool:
    if RUST_GAP:
        return _rg_verify_challenge(key, nonce, client_nonce, payload, sig)
    return _py_verify_challenge(key, nonce, client_nonce, payload, sig)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if RUST_GAP:
        return _rg_haversine_km(lat1, lon1, lat2, lon2)
    return _py_haversine_km(lat1, lon1, lat2, lon2)


def max_radius_km(rtt_ms: float, speed_km_per_ms: float = 200.0) -> float:
    if RUST_GAP:
        return _rg_max_radius_km(rtt_ms, speed_km_per_ms)
    return _py_max_radius_km(rtt_ms, speed_km_per_ms)


def is_within_radius(lat1: float, lon1: float, lat2: float, lon2: float,
                     rtt_ms: float, speed_km_per_ms: float = 200.0) -> bool:
    return haversine_km(lat1, lon1, lat2, lon2) <= max_radius_km(rtt_ms, speed_km_per_ms)


class KalmanLatencyTracker:
    """1-D Kalman filter for a device's latency sphere (pure-Python fallback)."""

    def __init__(self, q: float = 0.5, r: float = 4.0) -> None:
        if RUST_GAP:
            self._inner = _RustKalmanTracker(q, r)
            self._rust = True
        else:
            self._x = 0.0
            self._p = 1.0
            self._q = q
            self._r = r
            self._init = False
            self._rust = False

    def update(self, z: float) -> float:
        if self._rust:
            return self._inner.update(z)
        if not self._init:
            self._x, self._p, self._init = z, self._r, True
            return self._x
        p_pred = self._p + self._q
        k = p_pred / (p_pred + self._r)
        self._x += k * (z - self._x)
        self._p = (1.0 - k) * p_pred
        return self._x

    def estimate(self) -> float:
        return self._inner.estimate() if self._rust else self._x

    def is_anomalous(self, z: float, n_sigma: float = 5.0) -> bool:
        if self._rust:
            return self._inner.is_anomalous(z, n_sigma)
        p_pred = self._p + self._q
        return abs(z - self._x) > n_sigma * math.sqrt(p_pred + self._r)


# ---------------------------------------------------------------------------
# GAP protocol objects + authenticator (the seam to VRL-1)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GapChallenge:
    nonce: bytes
    issued_at: float


@dataclass(frozen=True)
class GapProof:
    tenant_id: str
    device_id: str
    nonce: bytes
    client_nonce: bytes
    signature: bytes


def _mix(reading: bytes, pin: str) -> bytes:
    """XOR a PIN-derived pad into the reading. Bit-local (not a hash), so the
    fuzzy extractor's error-correcting code can still correct reading noise."""
    pad = (hashlib.sha256(b"pin:" + pin.encode()).digest()
           * (len(reading) // 32 + 1))[:len(reading)]
    return bytes(r ^ p for r, p in zip(reading, pad))


class GapAuthenticator:
    """Composes physics + light + math into one passwordless handshake."""

    SPEED_KM_PER_MS = 200.0  # light in fiber (~2/3 c)

    def __init__(self, engine, vault, tenant_id: str, *, epoch: int = 1,
                 repeat: int = 3, home_lat: float = 40.7128,
                 home_lon: float = -74.0060, tolerance_sigma: float = 5.0) -> None:
        self.engine = engine
        self.vault = vault
        self.tenant_id = tenant_id
        self.epoch = epoch
        self.repeat = repeat
        self.home_lat = home_lat
        self.home_lon = home_lon
        self.tolerance_sigma = tolerance_sigma
        self.kalman = KalmanLatencyTracker()
        self.device_key: str | None = None
        self.helper: bytes | None = None

    def enroll_device(self, reading: bytes, pin: str, target_url: str,
                      db_connection_string: str) -> dict:
        """Enroll: fuzzy-extract a stable key and register it in the VRL-1 vault."""
        if len(reading) != _KEY_LEN * self.repeat:
            raise ValueError(f"reading must be exactly {_KEY_LEN * self.repeat} bytes")
        material = _mix(reading, pin)
        key, helper = fuzzy_generate(material, _KEY_LEN, self.repeat)
        self.device_key = key.hex()
        self.helper = helper
        info = self.vault.enroll_key(self.tenant_id, self.device_key, self.epoch,
                                     target_url, db_connection_string, scopes=["*"])
        return {"device_key": self.device_key, "helper": helper.hex(), **info}

    def issue_challenge(self) -> GapChallenge:
        return GapChallenge(os.urandom(16), time.time())

    def prove(self, reading: bytes, pin: str, challenge: GapChallenge) -> GapProof:
        """Prove: reproduce the key from a (possibly noisy) reading, sign the challenge."""
        if self.helper is None:
            raise RuntimeError("device not enrolled")
        material = _mix(reading, pin)
        key = fuzzy_reproduce(material, self.helper, _KEY_LEN, self.repeat)
        client_nonce = os.urandom(16)
        sig = sign_challenge(key, challenge.nonce, client_nonce, b"VRL4-GAP")
        device_id = hashlib.sha256(key).hexdigest()[:16]
        return GapProof(self.tenant_id, device_id, challenge.nonce, client_nonce, sig)

    def verify(self, proof: GapProof, *, device_lat: float, device_lon: float,
               rtt_ms: float) -> dict:
        """Verify physics (signature), light (RTT/geodesic), then math (VRL-1 ring)."""
        # 1. Physics: the device must possess the exact key (challenge signature).
        key = bytes.fromhex(self.device_key)
        if not verify_challenge(key, proof.nonce, proof.client_nonce, b"VRL4-GAP",
                                proof.signature):
            raise PermissionError("physics check failed: bad challenge signature")
        # 2. Light: Kalman latency sphere + geodesic physical bound.
        self.kalman.update(rtt_ms)
        if self.kalman.is_anomalous(rtt_ms, self.tolerance_sigma):
            raise PermissionError("light check failed: latency anomaly")
        if not is_within_radius(self.home_lat, self.home_lon, device_lat, device_lon,
                                rtt_ms, self.SPEED_KM_PER_MS):
            raise PermissionError("light check failed: distance bound")
        # 3. Math: exact integer-torus ring check via the existing VRL-1 engine.
        ts = int(time.time())
        nonce = f"gap-{ts}-{proof.client_nonce.hex()[:8]}"
        vproof = self.engine.make_proof(self.tenant_id, self.device_key, nonce, ts,
                                        "POST", "/gap/access", b"")
        return self.vault.authenticate(tenant_id=self.tenant_id, api_key=self.device_key,
                                       epoch=self.epoch, current_epoch=self.epoch,
                                       nonce=nonce, ts=ts, method="POST", path="/gap/access",
                                       body=b"", proof=vproof, now=float(ts))
