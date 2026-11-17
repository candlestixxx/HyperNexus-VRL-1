# Session Handoff — HyperNexus VRL-1

## Current state (2026-11-17)
- Version: `VERSION.md` = **1.8.0** (single source, read via `vrl1_version.app_version()`).
- Branch: `main` only; **no submodules**; remote `origin` = github.com/candlestixxx/HyperNexus-VRL-1.
- Tests: **70 passing** (`python -m pytest -q`). TestClient socket tests pass in this environment (no escalation needed).
- Tree is **clean**; all commits pushed through `cf4bc28`.

## What shipped this session (v1.4.0 → v1.8.0)
- **v1.4.0** (`2bdfae4`) — admin-gated enrollment (`x-vrl1-admin-key` / `VRL1_ADMIN_KEY`; demo key surfaced only in demo mode) + signed, tamper-evident vault persistence (HMAC over transparency root).
- **v1.5.0** (`e48e5c8`) — capability-attenuated agent tokens (`core/capability.py`): scope-subset, expiry, path-prefix, max-use caveats; `POST /secure/mint-token`; dispatch via `X-VRL1-Capability` or `Authorization: Bearer`.
- **v1.6.0** (`7f72383`) — CUSUM anomaly detection + fail-closed circuit breaker (`core/security_monitor.py`) per tenant + per shard; `/secure/circuits`.
- **v1.7.0** (`7dcce67`) — shared-store interfaces (`core/stores.py`): `NonceStore` / `CapabilityUsageStore` protocols + SQLite (WAL) backends; engine/vault now consume injected stores.
- **v1.8.0** (`cf4bc28`) — Feldman VSS threshold credential release (`core/threshold.py`): t-of-n Shamir over GF(Q) with Feldman commitments over RFC 3526 group 14.

## Architecture in one paragraph
`src/` = legacy production portal gateway (FastAPI, Fernet vault, router, DB pools, MCP JSON-RPC). `core/` = Tier-1 math/security engines: `vrl1_algo.py` (integer-torus engine, proof-of-possession, AEAD, replay), `secure_vault.py` (AEAD vault + admin gating + signed persistence + capability mint/auth + circuit breaker), `transparency.py` (Merkle log), `capability.py` (caveated tokens), `security_monitor.py` (CUSUM breaker), `stores.py` (shared-store backends), `threshold.py` (Feldman VSS). `api/gateway.py` = demo app (`create_app`) + secure app (`create_secure_app`). Entry points: `python main.py` (8000, portal), `uvicorn api.gateway:app` (8001, demo), `uvicorn api.gateway:create_secure_app --factory` (secure mode).

## What remains and why it's ordered this way
- **Redis/Postgres concrete drivers** — blocked: no Redis/Postgres service in this sandbox. The `NonceStore` / `CapabilityUsageStore` interfaces are ready in `core/stores.py`; implement + test against a live service.
- **KMS/HSM master-key custody** — blocked: requires an external provider choice.
- **Milestone 5 (research, multi-week, NOT short-term)**: Rust core port (no `cargo` in this sandbox), ZK ring-membership (field-native commitment), BFT multi-writer consensus, TLA+ model + independent pen test.

## Known flags (do not "fix" silently)
- Default master keys are hardcoded in `src/config.py` and `docker-compose.yml` for the *legacy* `src/` demo path. Secure mode (`create_secure_app`) already refuses demo keys unless `demo=True`. Purge only on explicit owner order.
- `ChaCha20Poly1305` substitutes for XChaCha20 (installed `cryptography` lacks XChaCha) — recorded in CHANGELOG v1.2.0.
- `docs/BENCHMARKS.md` numbers are micro-benchmarks only; no HTTP crucible vs Kong/Redis yet.
- Capability `max_uses` + CUSUM breaker state are per-process (in-memory or SQLite). Cross-process shared usage is supported via `SQLiteCapabilityUsageStore`; Redis/Postgres drivers are the remaining scale-out step.

## Resume commands
```powershell
pip install -r requirements.txt
python -m pytest -q
python benchmarks\bench_gateway.py
python main.py
# secure mode (needs real key material):
#   $env:VRL1_MASTER_KEY = ...; $env:VRL1_ADMIN_KEY = ...
#   uvicorn api.gateway:create_secure_app --factory --port 8001
```
Git pushes work with the current credentials; no special safe.directory config was needed this session.
