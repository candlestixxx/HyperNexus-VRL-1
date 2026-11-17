"""Rust-core vs pure-Python micro-benchmark.

Run: python benchmarks/bench_rust.py  (writes nothing; prints a table)

Measures the ported primitives (derive_coordinate, make_proof, spatialize_key)
through the engine (Rust path when _vrl1_core is built) against inline
pure-Python references, so the speedup is attributable to the Rust core.
"""
import hashlib
import hmac as _hmac
import struct
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import _rust
from core.vrl1_algo import VRL1ZeroTrustEngine
from core.vector_math import RadialVectorEngine

N = 20_000
TENANT_KEY = b"k" * 32
PROOF_KEY = b"p" * 32
KEY = "benchmark-key"


def _time(fn) -> float:
    t = time.perf_counter()
    for _ in range(N):
        fn()
    return (time.perf_counter() - t) / N * 1e6


# --- pure-Python references (same math, no Rust) -----------------------------
def py_derive():
    msg = (b"VRL1\x01" + struct.pack(">Q", len(b"tenant_a")) + b"tenant_a"
           + struct.pack(">Q", len(KEY.encode())) + KEY.encode()
           + struct.pack(">Q", 8) + struct.pack(">q", 1))
    return struct.unpack(">4Q", _hmac.new(TENANT_KEY, msg, hashlib.sha256).digest()[:32])


def py_proof():
    body_hash = hashlib.sha256(b"{}").digest()
    msg = (b"VRL1\x01" + struct.pack(">Q", len(b"n-1")) + b"n-1"
           + struct.pack(">Q", 8) + struct.pack(">q", 1234567890)
           + struct.pack(">Q", len(b"POST")) + b"POST"
           + struct.pack(">Q", len(b"/x")) + b"/x"
           + struct.pack(">Q", 32) + body_hash)
    return _hmac.new(PROOF_KEY, msg, hashlib.sha256).hexdigest()


def py_spatialize():
    digest = hashlib.sha256(KEY.encode()).digest()
    frac = int.from_bytes(digest[:8], "big") / float(2**64 - 1)
    radius = 100.0 * (1.0 + frac)
    denom = float(2**64 - 1)
    return [2.0 * np.pi * (int.from_bytes(digest[8 + i * 8:16 + i * 8], "big") / denom)
            for i in range(3)]


def main() -> None:
    engine = VRL1ZeroTrustEngine(b"bench-master-key-32-bytes-minimum!")
    engine._tenant_keys["tenant_a"] = TENANT_KEY  # warm HKDF cache
    fengine = RadialVectorEngine(dimensions=4, ring_width=100.0)
    rust = _rust.RUST_AVAILABLE

    print(f"ops measured: {N} | rust core built: {rust}")
    rows = []

    # derive_coordinate
    rust_us = _time(lambda: engine.derive_coordinate("tenant_a", KEY, 1)) if rust else None
    py_us = _time(py_derive)
    rows.append(("derive_coordinate", rust_us, py_us))

    # make_proof
    rust_us2 = _time(lambda: engine.make_proof("tenant_a", KEY, "n-1", 1234567890, "POST", "/x", b"{}")) if rust else None
    py_us2 = _time(py_proof)
    rows.append(("make_proof", rust_us2, py_us2))

    # spatialize_key (d=4)
    rust_us3 = _time(lambda: fengine.spatialize_key(KEY)) if rust else None
    py_us3 = _time(py_spatialize)
    rows.append(("spatialize_key", rust_us3, py_us3))

    print(f"{'operation':<18} {'rust us/op':>12} {'python us/op':>14} {'speedup':>8}")
    for name, r, p in rows:
        speedup = f"{p / r:5.1f}x" if r else "  n/a"
        r_s = f"{r:12.2f}" if r else "         n/a"
        print(f"{name:<18} {r_s} {p:14.2f} {speedup:>8}")


if __name__ == "__main__":
    main()
