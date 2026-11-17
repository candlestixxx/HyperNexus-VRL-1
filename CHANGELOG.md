# Changelog — HyperNexus VRL-1

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.12.0] - 2026-11-17

### Added
- **KMS master-key custody (Vault)** (`core/kms.py`): `MasterKeySource` interface + `VaultMasterKeySource` (reads the master key from Vault KV v2). `create_secure_app` now prefers Vault (`VRL1_VAULT_ADDR` + `VRL1_VAULT_TOKEN`) over the env/demo fallback, so production key material can live in a KMS instead of config. Verified against a local Vault dev server.
- 3 new tests (86 total): key fetch, bad-token rejection, and end-to-end secure-app bootstrapping from Vault.

## [1.11.0] - 2026-11-17

### Added
- **PostgreSQL shared-store drivers** (`core/stores_postgres.py`): `PostgresNonceStore` (atomic `INSERT ... ON CONFLICT DO NOTHING`) and `PostgresCapabilityUsageStore` (atomic `... ON CONFLICT DO UPDATE ... RETURNING used`), drop-in for the `NonceStore` / `CapabilityUsageStore` protocols. Verified against a real local PostgreSQL 18 via `embedded-postgres`.
- 4 new tests (83 total): nonce replay/expiry, cross-instance sharing, usage budget, and engine integration over Postgres.

## [1.10.0] - 2026-11-17

### Added
- **Redis shared-store drivers** (`core/stores_redis.py`): `RedisNonceStore` (atomic `SET NX EX`) and `RedisCapabilityUsageStore` (atomic `INCR`), drop-in for the `NonceStore` / `CapabilityUsageStore` protocols. The `redis` import is lazy so the rest of the package works without it; verified against `fakeredis` (no server). The Postgres driver remains (same interface, needs a live server to verify).
- 4 new tests (79 total): replay/expiry, cross-instance sharing, usage budget, and engine integration over Redis.

## [1.9.1] - 2026-11-17

### Changed
- **Rust core releases the GIL** around its HMAC/SHA-256 work (`Python::detach`), so concurrent Python threads can overlap on derivation/proof instead of serializing on the interpreter lock. Measured honestly: at ~2–3 µs/op the thread-coordination overhead dominates, so parallel throughput only peaks ~1.1–1.5× at 2–4 threads (where pure Python stays GIL-bound/flat) and degrades past core count. The reliable win remains the ~2× single-thread speedup from v1.9.0.
- Added `benchmarks/bench_parallel.py` for the thread-scaling measurement.

## [1.9.0] - 2026-11-17

### Added
- **Rust core (PyO3)** (`rust/vrl1_core/`): ports `derive_coordinate`, `make_proof`, and `spatialize_key` (d=4) to Rust. `core/_rust.py` imports the compiled `_vrl1_core` extension when available and falls back to pure Python otherwise. Measured ~2–2.5× speedup on the ported primitives (dev laptop, single core).
- Engine `proof_key` is now cached (it feeds every gateway `verify_request`, so the per-call HKDF was the dominant cost).
- `benchmarks/bench_rust.py` + 5 parity tests (75 total) proving Rust output equals the Python reference.

## [1.8.0] - 2026-11-17

### Added
- **Threshold (Feldman VSS) credential release** (`core/threshold.py`): t-of-n Shamir secret sharing over GF(Q) with Feldman commitments over RFC 3526 group 14 (2048-bit safe prime). `split_secret()` shards a credential, `verify_share()` detects a corrupted share or dishonest dealer before release, and `reconstruct()` recovers the secret from any t shares — so no single node holds the whole credential.
- 6 new tests (70 total): group-constant sanity, split/verify/reconstruct roundtrip, tampered-share rejection, insufficient-share rejection, deal independence, and degenerate-input rejection.

## [1.7.0] - 2026-11-17

### Added
- **Shared-store interfaces** (`core/stores.py`): `NonceStore` and `CapabilityUsageStore` protocols with verifiable SQLite (WAL) backends. The engine (`VRL1ZeroTrustEngine(nonce_store=...)`) and vault (`SecureRadialVault(usage_store=...)`) now consume these interfaces, so the hot-path replay and capability-usage ledgers can move to a shared store (and later Redis/Postgres) without touching call sites.
- 5 new tests (64 total): SQLite nonce replay/expiry/shared-across-instances, capability usage budget, engine with a shared nonce store, and cross-instance capability budget exhaustion.

## [1.6.0] - 2026-11-17

### Added
- **CUSUM anomaly detection + circuit breaker** (`core/security_monitor.py`): a fail-closed brute-force defense. Auth failures feed a per-tenant + per-shard CUSUM control chart; crossing a threshold opens a circuit for a cooldown window. While open, the vault rejects before the proof/nonce machinery, so a flood is shed cheaply and the victim's nonce ledger is never burned.
- `SecureRadialVault` accepts an injectable `monitor`; `open_circuits()` exposes open breakers. Gateway `/health` and a new `/secure/circuits` endpoint surface them; `/secure/ui` gains a circuit-breaker status panel.
- 4 new tests (59 total): CUSUM trip/recovery, baseline tolerance, cooldown reporting, and fail-closed-without-burning-nonce.

## [1.5.0] - 2026-11-17

### Added
- **Capability-attenuated agent tokens** (`core/capability.py`): admin-minted, HMAC-signed tokens caveated by a scope subset, an expiry, an optional path prefix, and an optional max-use budget. Agents dispatch with only the token (`X-VRL1-Capability` or `Authorization: Bearer`), never the raw tenant key.
- Vault integration: `SecureRadialVault.mint_agent_token()` (mints against the latest-epoch enrollment; rejects scope escalation) and `authenticate_agent_token()` (verifies signature → expiry → path → scope → budget, then AEAD-opens the record). A `"*"` enrollment scope grants any attenuated scope.
- Gateway: admin-gated `POST /secure/mint-token`; the dispatch path accepts capability tokens before falling back to key+proof; `/secure/ui` gains mint + capability-dispatch controls.
- 11 new tests (55 total): roundtrip/tamper/expiry, usage ledger, scope escalation, path prefix, max-uses, gateway mint, and forged-token 403.

## [1.4.0] - 2026-11-17

### Added
- **Admin-gated enrollment (secrets-hygiene hardening)**: `/secure/enroll` now requires an `x-vrl1-admin-key` header matching `admin_key` param → `VRL1_ADMIN_KEY` env → demo-generated key. Missing/wrong key returns 403 before any vault mutation. A demo-generated key is surfaced via `/secure/demo-admin-key` and stderr **only** in demo mode; in real mode that endpoint returns 404 and the key never travels over HTTP.
- **Signed, tamper-evident vault persistence**: `SecureRadialVault(persistence_path=...)` atomically persists rings, AEAD-sealed records, and transparency leaves. The persisted transparency root carries an HMAC signature (`VRL1ZeroTrustEngine.sign_root` / `verify_root_signature`); reload verifies signature + root and refuses rolled-back or forged state files.
- `MerkleLog.export_state()` / `load_state()` for log serialization.
- 4 new tests (44 total): admin-key gating (missing + wrong), demo key surfacing + hiding, persistence reload, and rollback/tamper rejection.

## [1.3.0] - 2026-11-16

### Added
- **Secure gateway integration (P1/P7/P8)**: `create_secure_app` in `api/gateway.py` wires `SecureRadialVault` to HTTP — `/secure/enroll` (key shown once), `/secure/ui` demo page, proof-header dispatch (`X-VRL1-*`), 403 with upstream never called on failure. Refuses to start without `VRL1_MASTER_KEY` unless `demo=True`.
- **Merkle transparency log (P2)**: `core/transparency.py`, append-only enrollment log with inclusion proofs; root exposed at `/health` and on enroll.
- **Invariant fuzz test (P3)**: 50-round cross-tenant/tamper property test in `tests/test_secure_gateway.py` (5 new tests, 40 total).
- **Single version source (P4)**: `vrl1_version.py` reads `VERSION.md`; `src/config.py` and the secure gateway consume it.
- **Benchmark harness (P5)**: `benchmarks/bench_gateway.py` + measured results in `docs/BENCHMARKS.md` (no extrapolated claims).
- **CI (P6)**: `.github/workflows/tests.yml` runs the full suite on push/PR.
- ROADMAP.md/TODO.md rewritten from live audit.

## [1.2.0] - 2026-11-16

### Added — Tier-1 corrected zero-trust engine
- `core/vrl1_algo.py`: `d=4` uint64 integer-torus coordinates (static per epoch — nonce removed from derivation, fixing the pasted prototype's fatal flaw), HKDF per-tenant keys, per-request HMAC proof-of-possession (stolen vectors are useless), tenant-scoped expiring nonce ledger that burns nonces only after full verification, length-prefixed canonical encoding, ChaCha20-Poly1305 AEAD records bound to (tenant, radius, shards, epoch, scopes).
- `core/secure_vault.py`: disjoint-ring tenant registration, rejection-sampled generated keys, out-of-ring BYO key refusal, shard-collision panic, dual-epoch (rotation) authentication.
- `tests/test_vrl1_algo.py`: 7 tests — end-to-end auth, stolen-vector rejection, replay + nonce-poisoning resistance, cross-ring/overlap refusal, AEAD move/tamper/scope-escalation failure, collision panic. 35 tests total passing.
- `docs/SPEC.md`: locked parameter spec, defensible pitch wording, measured micro-benchmark, honest audit-readiness gap list.
- Note: XChaCha20-Poly1305 substituted with ChaCha20Poly1305 (installed `cryptography` build lacks XChaCha); same AEAD family, shorter nonce — recorded here, not hidden.

## [1.1.0] - 2026-11-16

### Added
- **VRL-1 Math Core (`core/`)**: `RadialVectorEngine` implementing Proofs I–III (SHA-256 spatilization to `(r, θ)`, disjoint-ring radial gate, O(1)-in-N angular routing) with numpy; `RadialVault` in-memory vault indexed by angular shard with overlap-rejecting tenant registration.
- **Standalone Async Gateway (`api/gateway.py`)**: `POST /mcp/dispatch/{path:path}` resolving `X-API-Key` at the math layer, forwarding via `httpx.AsyncClient`, instant 403 with no DB/log write on rejection.
- **Geometric Proof Tests**: `tests/test_zero_trust.py` + `tests/test_gateway_dispatch.py` (10 new tests; 28 total passing), including cross-tenant vector rejection and upstream-never-called assertions.
- **Docs**: `docs/MATHEMATICS.md` (proofs + honest limits), `MANIFESTO.md` (investor/partner narrative), `LLM_BUILD_INSTRUCTIONS.md` (agent build directive).
- `numpy` added to `requirements.txt`.

## [1.0.0] - 2026-11-14

### Added
- **Core Architecture**:
  - High-throughput asynchronous FastAPI control plane in `src/main.py`.
  - Configurable settings engine with Pydantic v2 `SettingsConfigDict` in `src/config.py`.
- **Radial Vector Secret Vault (`src/vault/`)**:
  - Mathematical tree-ring radial vector coordinate derivation $(r, \theta, z)$.
  - Zero cross-tenant data leakage guarantees with envelope encryption via Fernet & PBKDF2HMAC.
  - Runtime hot-registration and atomic persistence to `data/radial_vault.json`.
- **Dynamic AI Switchboard Router (`src/router/`)**:
  - Multi-vector tenant resolution across `X-API-Key`, Bearer tokens, Host domains, `X-Tenant-ID`, and query/body fallbacks.
  - Per-tenant token-bucket rate limiter enforcing traffic quotas and preventing noisy-neighbor degradation.
  - Upstream HTTP proxy forwarding with simulated loopback fallback for offline testing.
- **Multi-Tenant Database Pool Manager (`src/db/`)**:
  - Dynamic connection pooling per tenant schema.
  - Tenant-isolated SQLite transaction audit logging (`data/audit_{company_id}.sqlite3`).
- **Model Context Protocol (MCP) Server (`src/mcp/`)**:
  - JSON-RPC 2.0 compliant MCP server endpoints (`/mcp/rpc`, `/mcp/tools`, `/mcp/context`).
  - Isolated AI agent context buffers for Hermes Agent and Ollama swarms.
- **Developer Portal UI (`src/portal/index.html`)**:
  - Modern, responsive dark-mode Single Page Application.
  - Interactive HTML5 Canvas Radial Vector visualizer rendering concentric security rings.
  - Dynamic API Switchboard simulator with real-time latency and payload inspection.
  - Zero-downtime tenant onboarding form.
  - Live database audit ledger viewer and MCP capability monitor.
- **Testing & Tooling**:
  - 18 comprehensive pytest test cases covering vault security, routing, MCP hooks, and end-to-end API flows.
  - Automated deployment scripts: `start.bat`, `start.sh`, `Dockerfile`, `docker-compose.yml`.
  - Comprehensive documentation suite: `BUSINESS_PLAN.md`, `VISION.md`, `MEMORY.md`, `DEPLOY.md`, `IDEAS.md`, `ROADMAP.md`, `TODO.md`, `HANDOFF.md`, `README.md`.
