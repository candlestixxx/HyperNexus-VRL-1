"""Rust core (PyO3) parity + wiring tests.

These prove the Rust port matches the pure-Python reference math exactly.
Skipped automatically when the `_vrl1_core` extension is not built (e.g. CI).
"""
import hashlib
import hmac as _hmac
import struct

import numpy as np
import pytest

from core import _rust

pytestmark = pytest.mark.skipif(
    not _rust.RUST_AVAILABLE, reason="Rust core not built (_vrl1_core missing)")


# Reference pure-Python implementations (kept inline so they don't route
# through the same Rust branch under test).
def _py_derive(tenant_key, tenant_id, api_key, epoch):
    msg = b"VRL1\x01" + struct.pack(">Q", len(tenant_id.encode())) + tenant_id.encode() \
        + struct.pack(">Q", len(api_key.encode())) + api_key.encode() \
        + struct.pack(">Q", 8) + struct.pack(">q", epoch)
    digest = _hmac.new(tenant_key, msg, hashlib.sha256).digest()
    return struct.unpack(">4Q", digest[:32])


def _py_proof(proof_key, nonce, ts, method, path, body):
    body_hash = hashlib.sha256(body).digest()
    msg = b"VRL1\x01" + struct.pack(">Q", len(nonce.encode())) + nonce.encode() \
        + struct.pack(">Q", 8) + struct.pack(">q", ts) \
        + struct.pack(">Q", len(method.encode())) + method.upper().encode() \
        + struct.pack(">Q", len(path.encode())) + path.encode() \
        + struct.pack(">Q", 32) + body_hash
    return _hmac.new(proof_key, msg, hashlib.sha256).hexdigest()


def _py_spatialize(api_key):
    digest = hashlib.sha256(api_key.encode("utf-8")).digest()
    frac = int.from_bytes(digest[:8], "big") / float(2**64 - 1)
    radius = 100.0 * (1.0 + frac)
    payload = digest[8:32]
    chunk = 8
    denom = float(2 ** (chunk * 8) - 1)
    angles = [
        2.0 * np.pi * (int.from_bytes(payload[i * chunk:(i + 1) * chunk], "big") / denom)
        for i in range(3)
    ]
    return radius, angles


def test_rust_derive_coordinate_matches_python():
    tenant_key = b"k" * 32
    for tenant, key, epoch in [("tenant_a", "some-key", 1),
                               ("tenant_b", "other-key", 7),
                               ("tenant_a", "some-key", 8)]:
        py = _py_derive(tenant_key, tenant, key, epoch)
        rust = _rust.rust_derive_coordinate(tenant_key, tenant, key, epoch)
        assert (rust[0], tuple(rust[1])) == (py[0], py[1:])


def test_rust_make_proof_matches_python():
    proof_key = b"p" * 32
    for nonce, ts, method, path, body in [
        ("n-1", 1234567890, "POST", "/mcp/dispatch/leads", b'{"x":1}'),
        ("n-2", 0, "get", "/", b""),
        ("n-3", -5, "PUT", "/a/b", b"\x00\x01\x02"),
    ]:
        assert _rust.rust_make_proof(proof_key, nonce, ts, method, path, body) \
            == _py_proof(proof_key, nonce, ts, method, path, body)


def test_rust_spatialize_key_matches_python():
    for key in ["excel_legacy_key_7742", "ub_live_key_9901_hypernexus_vrl1", "demo"]:
        r_radius, r_angles = _rust.rust_spatialize_key(key)
        p_radius, p_angles = _py_spatialize(key)
        assert r_radius == p_radius
        assert np.allclose(r_angles, p_angles, rtol=1e-12, atol=1e-12)


def test_engine_wiring_uses_rust_and_stays_consistent():
    from core.vrl1_algo import VRL1ZeroTrustEngine
    engine = VRL1ZeroTrustEngine(b"test-master-key-32-bytes-minimum!!")
    key = "wired-key"
    # Engine's derive_coordinate routes through Rust; output equals reference.
    r, s = engine.derive_coordinate("tenant_a", key, 3)
    py = _py_derive(engine._tenant_key("tenant_a"), "tenant_a", key, 3)
    assert (r, tuple(s)) == (py[0], py[1:])
    # Engine's make_proof routes through Rust; output equals reference.
    proof = engine.make_proof("tenant_a", key, "n", 99, "POST", "/x", b"b")
    assert proof == _py_proof(engine.proof_key("tenant_a", key), "n", 99, "POST", "/x", b"b")


def test_float_engine_wiring_uses_rust_and_stays_consistent():
    from core.vector_math import RadialVectorEngine
    engine = RadialVectorEngine(dimensions=4, ring_width=100.0)
    radius, angles = engine.spatialize_key("some-key")
    p_radius, p_angles = _py_spatialize("some-key")
    assert radius == p_radius
    assert np.allclose(angles, p_angles, rtol=1e-12, atol=1e-12)
