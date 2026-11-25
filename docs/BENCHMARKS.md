# Benchmarks — measured, not claimed

Harness: [benchmarks/bench_gateway.py](../benchmarks/bench_gateway.py) · 20,000 ops, dev laptop, Python 3.14, single core. Re-run before quoting any number externally.

| Operation | Measured |
|---|---|
| `derive_coordinate` (HKDF cached tenant key + HMAC) | 12.37 µs/op |
| `verify_request` proof-fail path (early exit) | 29.12 µs/op |
| Bare dict shard lookup (Redis-class baseline proxy) | 0.093 µs/op |

Honest reading: Tier-1 verification costs tens of microseconds — negligible against network + DB latency in a real dispatch (milliseconds), and ~2–3 orders of magnitude above a bare in-memory lookup. That gap is the Rust port's job (ROADMAP Milestone 5). No energy or throughput-superiority claim is made from this data; a full HTTP gateway-vs-Kong/Redis benchmark remains the Phase-1 crucible owed before any external performance pitch.

## Rust core (v1.9.0)

Harness: [benchmarks/bench_rust.py](../benchmarks/bench_rust.py) · 20,000 ops, dev laptop, Python 3.14, single core. `_vrl1_core` built with `maturin build --release` (PyO3 0.30, Rust 1.100, MSVC). Single-core timings are noisy across runs (±~30%); ranges below.

| Operation | Rust us/op | Pure-Python us/op | Speedup |
|---|---|---|---|
| `derive_coordinate` | ~4–8 | ~13–14 | ~2× |
| `make_proof` | ~4–7 | ~9–16 | ~2–2.5× |
| `spatialize_key` (d=4) | ~1.7–2.1 | ~4.4–5.1 | ~2.5–3× |

Honest reading: the Rust port roughly halves the cost of the ported crypto primitives. It does not reach the ~0.09 µs bare-dict baseline — the remaining gap is HMAC itself plus the Python↔Rust call boundary, not a table scan.

### Parallel derivation (GIL release, v1.9.1)

The Rust functions release the GIL around the HMAC (`Python::detach`). Measured across thread counts (200k ops, dev laptop, noisy single-core timings): Rust throughput peaks ~1.1–1.5× at 2–4 threads where pure Python stays flat (GIL-bound), and both degrade past the core count from oversubscription. Honest read: at ~2–3 µs/op the thread-coordination overhead dominates, so the reliable win remains the ~2× single-thread speedup; releasing the GIL is the correct foundation but only pays off once per-op work grows or callers batch.

## HTTP gateway (v1.17.0)

Harness: [benchmarks/bench_http.py](../benchmarks/bench_http.py) · secure-gateway dispatch, in-process ASGI + mock upstream, 2,000 requests, concurrency 8, dev laptop (noisy single-core timings).

| Mode | Throughput | p50 | p95 |
|---|---|---|---|
| Rust core | ~350–435 req/s | ~1.9–2.4 ms | ~4.4–5.7 ms |
| Pure Python | ~410–421 req/s | ~2.0–2.1 ms | ~4.4–4.9 ms |

Honest reading: at the full-request level there is no reliable Rust-vs-Python difference — run-to-run variance exceeds the gap. That is expected: the ported crypto is a few microseconds of a ~2 ms request dominated by ASGI/JSON/upstream/AEAD/nonce/breaker overhead. The Rust win is real only at the primitive level (2×, above). The Kong/Nginx+Redis baseline comparison remains the outstanding Phase-1 crucible before any external throughput claim.

## HTTP crucible (v1.19.x)

Harness: [benchmarks/bench_crucible.py](../benchmarks/bench_crucible.py) · secure-gateway dispatch vs a bare key-lookup gateway, in-process ASGI + mock upstream, 2,000 requests, concurrency 8, dev laptop.

| Gateway | Throughput | p50 | p95 |
|---|---|---|---|
| Bare dict lookup (Redis-class proxy) | ~1,050–1,090 req/s | ~870–890 µs | ~1.0–1.1 ms |
| VRL-1 secure (torus + proof + AEAD) | ~444–448 req/s | ~2.16 ms | ~2.7–2.9 ms |

Honest reading: VRL-1's full zero-trust path costs **~2.4× a bare key lookup** at the HTTP level — the price of exact-torus verification, per-request proof-of-possession, and AEAD record opening, all in Python. That is the defensible, non-marketing number. A real Kong/Nginx+Redis run is documented in [deploy/](../deploy/) and [benchmarks/run_crucible_linux.sh](../benchmarks/run_crucible_linux.sh) (needs Linux/WSL + Docker).
