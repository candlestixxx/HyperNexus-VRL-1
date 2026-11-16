# Benchmarks — measured, not claimed

Harness: [benchmarks/bench_gateway.py](../benchmarks/bench_gateway.py) · 20,000 ops, dev laptop, Python 3.14, single core. Re-run before quoting any number externally.

| Operation | Measured |
|---|---|
| `derive_coordinate` (HKDF cached tenant key + HMAC) | 12.37 µs/op |
| `verify_request` proof-fail path (early exit) | 29.12 µs/op |
| Bare dict shard lookup (Redis-class baseline proxy) | 0.093 µs/op |

Honest reading: Tier-1 verification costs tens of microseconds — negligible against network + DB latency in a real dispatch (milliseconds), and ~2–3 orders of magnitude above a bare in-memory lookup. That gap is the Rust port's job (ROADMAP Milestone 5). No energy or throughput-superiority claim is made from this data; a full HTTP gateway-vs-Kong/Redis benchmark remains the Phase-1 crucible owed before any external performance pitch.
