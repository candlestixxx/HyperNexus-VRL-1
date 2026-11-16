"""Measured micro-benchmark: Tier-1 derivation/verification vs bare dict lookup.

Run: python benchmarks/bench_gateway.py  (writes nothing; prints a table)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.vrl1_algo import Ring, VRL1ZeroTrustEngine

N = 20_000


def _time(fn) -> float:
    t = time.perf_counter()
    for _ in range(N):
        fn()
    return (time.perf_counter() - t) / N * 1e6


def main() -> None:
    e = VRL1ZeroTrustEngine(b"bench-master-key-32-bytes-minimum!")
    key = e.generate_api_key()
    radius, shards = e.derive_coordinate("tenant_a", key, 1)
    ring = Ring(0, 1 << 64)
    store = {shards: "x"}
    print(f"ops measured: {N}")
    print(f"derive_coordinate : {_time(lambda: e.derive_coordinate('tenant_a', key, 1)):8.2f} us/op")
    print(f"verify (range+shard): {_time(lambda: e.verify_request(tenant_id='tenant_a', api_key=key, epoch=1, current_epoch=1, ring=ring, target_shards=shards, nonce='x', ts=int(time.time()), method='POST', path='/x', body=b'', proof='00')):8.2f} us/op (proof-fail path)")
    print(f"dict shard lookup : {_time(lambda: store.get(shards)):8.3f} us/op")


if __name__ == "__main__":
    main()
