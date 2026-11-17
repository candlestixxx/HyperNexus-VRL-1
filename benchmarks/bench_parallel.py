"""Parallel derivation benchmark: GIL-release scaling (Rust) vs pure Python.

Run: python benchmarks/bench_parallel.py  (writes nothing; prints a table)

The Rust core releases the GIL around the HMAC, so concurrent Python threads
can overlap on the crypto instead of serializing on the interpreter lock.
This measures throughput across thread counts for the raw Rust primitive
vs. the equivalent pure-Python reference.
"""
import hashlib
import hmac as _hmac
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import _rust

TOTAL = 200_000
TENANT_KEY = b"k" * 32
KEY = "benchmark-key"


def py_derive():
    msg = (b"VRL1\x01" + struct.pack(">Q", len(b"tenant_a")) + b"tenant_a"
           + struct.pack(">Q", len(KEY.encode())) + KEY.encode()
           + struct.pack(">Q", 8) + struct.pack(">q", 1))
    return struct.unpack(">4Q", _hmac.new(TENANT_KEY, msg, hashlib.sha256).digest()[:32])


def rust_derive():
    return _rust.rust_derive_coordinate(TENANT_KEY, "tenant_a", KEY, 1)


def _run(fn, workers: int) -> float:
    per = TOTAL // workers
    def work(_):
        for _ in range(per):
            fn()
    t = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, range(workers)))
    return TOTAL / (time.perf_counter() - t)


def main() -> None:
    print(f"total ops: {TOTAL} | rust core built: {_rust.RUST_AVAILABLE}")
    if not _rust.RUST_AVAILABLE:
        print("rust core not built; python-only")
    print(f"{'threads':<8} {'rust ops/s':>12} {'python ops/s':>14}")
    for k in (1, 2, 4, 8):
        r = _run(rust_derive, k) if _rust.RUST_AVAILABLE else None
        p = _run(py_derive, k)
        r_s = f"{r:12,.0f}" if r else "         n/a"
        print(f"{k:<8} {r_s} {p:14,.0f}")


if __name__ == "__main__":
    main()
