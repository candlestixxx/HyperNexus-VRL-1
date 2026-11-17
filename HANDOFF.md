# Session Handoff — HyperNexus VRL-1

## Current state (2026-11-17)
- Version: `VERSION.md` = **1.14.0** (single source, read via `vrl1_version.app_version()`).
- Branch: `main` only; **no submodules**; remote `origin` = github.com/candlestixxx/HyperNexus-VRL-1.
- Tests: **97 passing** (`python -m pytest -q`). Rust/Redis/Postgres/Vault tests skip when their tooling or test deps are missing.
- Tree is **clean**; all commits pushed through `ee59422`.

## What shipped this session (v1.4.0 → v1.9.0)
- **v1.4.0** (`2bdfae4`) — admin-gated enrollment + signed, tamper-evident vault persistence.
- **v1.5.0** (`e48e5c8`) — capability-attenuated agent tokens (`core/capability.py`).
- **v1.6.0** (`7f72383`) — CUSUM anomaly detection + fail-closed circuit breaker (`core/security_monitor.py`).
- **v1.7.0** (`7dcce67`) — shared-store interfaces (`core/stores.py`) + SQLite (WAL) backends.
- **v1.8.0** (`cf4bc28`) — Feldman VSS threshold credential release (`core/threshold.py`).
- **v1.9.0** (`ee59422`) — Rust core (PyO3) port (`rust/vrl1_core/`) of `derive_coordinate`, `make_proof`, `spatialize_key`; `core/_rust.py` auto-detects it with a pure-Python fallback. `proof_key` is now cached.
- **v1.9.1** — Rust functions release the GIL (`Python::detach`) + `benchmarks/bench_parallel.py` (honest read: ~2× single-thread win is the reliable gain; parallel scaling is small/noisy at ~2 µs/op).
- **v1.10.0** — Redis shared-store drivers (`core/stores_redis.py`: `RedisNonceStore`, `RedisCapabilityUsageStore`), verified via `fakeredis`.
- **v1.11.0** — PostgreSQL shared-store drivers (`core/stores_postgres.py`: `PostgresNonceStore`, `PostgresCapabilityUsageStore`), verified via `embedded-postgres`.
- **v1.12.0** — KMS master-key custody (`core/kms.py`: `VaultMasterKeySource`), verified against a local Vault dev server.
- **v1.13.0** — ZK ring membership (`core/ring_sig.py`: Schnorr ring signature, AOS).
- **v1.14.0** — BFT consensus core (`core/bft.py`: PBFT 3-phase agreement).

## Architecture in one paragraph
`src/` = legacy production portal gateway (FastAPI, Fernet vault, router, DB pools, MCP JSON-RPC). `core/` = Tier-1 engines: `vrl1_algo.py` (integer-torus engine, proof-of-possession, AEAD, replay, cached proof/tenant keys, optional Rust), `secure_vault.py` (AEAD vault + admin gating + signed persistence + capability mint/auth + circuit breaker), `transparency.py` (Merkle log), `capability.py` (caveated tokens), `security_monitor.py` (CUSUM breaker), `stores.py` (shared-store backends), `threshold.py` (Feldman VSS), `_rust.py` (PyO3 shim). `api/gateway.py` = demo app (`create_app`) + secure app (`create_secure_app`). Entry points: `python main.py` (8000), `uvicorn api.gateway:app` (8001, demo), `uvicorn api.gateway:create_secure_app --factory` (secure mode).

## What remains and why it's ordered this way
- **Field-native Poseidon commitment designed with the circuit** — the SNARK-friendliness refinement of the ZK ring-membership work (the "not a hash swap" part). The sound ring-membership proof (`core/ring_sig.py`) is done.
- **PBFT view-change** — primary-failure liveness recovery (the agreement/safety core in `core/bft.py` is done).
- **TLA+ model + independent pen test** — the remaining Milestone 5 item.
- **HSM hardware integration** — optional provider-specific follow-on to the Vault custody path (same `MasterKeySource` interface).

## Known flags (do not "fix" silently)
- Default master keys are hardcoded in `src/config.py` and `docker-compose.yml` for the *legacy* `src/` demo path. Secure mode refuses demo keys unless `demo=True`. Purge only on explicit owner order.
- `ChaCha20Poly1305` substitutes for XChaCha20 (recorded in CHANGELOG v1.2.0).
- `docs/BENCHMARKS.md` numbers are micro-benchmarks only; no HTTP crucible vs Kong/Redis yet.
- Capability `max_uses` + CUSUM breaker are per-process (in-memory or SQLite); cross-process usage works via `SQLiteCapabilityUsageStore`.
- The Rust extension is **not committed** (platform-specific); only `rust/vrl1_core/` source is. Build it locally per below.

## Resume commands
```powershell
pip install -r requirements.txt
python -m pytest -q

# Rust core (optional, ~2x on ported primitives):
pip install maturin
cd rust/vrl1_core
maturin build --release
pip install --force-reinstall target/wheels/vrl1_core-*.whl
cd ../..

python benchmarks\bench_gateway.py
python benchmarks\bench_rust.py
python benchmarks\bench_parallel.py
python main.py
# secure mode:
#   $env:VRL1_MASTER_KEY = ...; $env:VRL1_ADMIN_KEY = ...
#   uvicorn api.gateway:create_secure_app --factory --port 8001
```
Git pushes work with the current credentials.
