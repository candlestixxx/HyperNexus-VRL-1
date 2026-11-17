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

Honest reading: the Rust port roughly halves the cost of the ported crypto primitives. It does not reach the ~0.09 µs bare-dict baseline — the remaining gap is HMAC itself plus the Python↔Rust call boundary, not a table scan. The larger structural win (releasing the GIL for parallel derivation) is not yet exercised.
