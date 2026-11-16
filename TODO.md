# Granular Short-Term Tasks — HyperNexus VRL-1

All P1–P8 items shipped in v1.3.0 (see CHANGELOG.md). Remaining work lives in ROADMAP.md Milestones 4–5 (enterprise/research tiers), each too large for one work cycle.

- [x] P1 Secure gateway integration (`SecureRadialVault` + `X-VRL1-*` proof headers in `api/gateway.py`)
- [x] P2 Merkle transparency log (`core/transparency.py`)
- [x] P3 Invariant fuzz test (`tests/test_secure_gateway.py`)
- [x] P4 Single version source (`vrl1_version.py` reads `VERSION.md`)
- [x] P5 Benchmark harness (`benchmarks/bench_gateway.py`, `docs/BENCHMARKS.md`)
- [x] P6 CI workflow (`.github/workflows/tests.yml`)
- [x] P7 Secure-mode demo UI (`/secure/ui`)
- [x] P8 Secrets hygiene (secure mode requires `VRL1_MASTER_KEY` or explicit `demo=True`)
