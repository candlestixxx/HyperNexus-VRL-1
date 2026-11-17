# Architectural Memory & Codebase Traits — HyperNexus VRL-1

## 1. Architectural Observations
- **FastAPI Async Core**: Built on Python 3.10+ async/await primitives with `httpx.AsyncClient` connection pools. This guarantees maximum non-blocking I/O throughput during proxy dispatch.
- **Radial Vector Mathematics**:
  - The polar coordinate tuple $(r, \theta, z)$ maps tenant isolation:
    - Radius $r$ directly indexes security rings ($0.5$ for Core, $1.0$ for United Beats, $1.5$ for Pro Realty, $2.0$ for Standard).
    - Angle $\theta \in [0, 2\pi)$ distributes tenants uniformly across the ring via SHA-256 modulo projection.
    - Depth $z$ represents the rotation depth for PBKDF2/Fernet envelope cipher keys.
- **Zero Cross-Tenant Leakage Guarantee**:
  - Each company has its own isolated audit database (`data/audit_{company_id}.sqlite3`) and dedicated database session pool in `MultiTenantDBPoolManager`.
  - Context windows in `MCPAgentBridge` are mapped strictly by `company_id`.
- **Dynamic Onboarding**:
  - Registering a tenant via `POST /api/v1/tenants` updates `_registry_by_hash`, `_company_to_hash`, and `_domain_to_hash` atomically under an `RLock`, followed by atomic disk persistence (`data/radial_vault.json`).

## 2. Codebase Traits & Conventions
- **Strict Typing**: Full Pydantic v2 schemas across requests, models, and telemetry.
- **Deprecation Cleanliness**: Avoided `datetime.utcnow()` in favor of `datetime.now(timezone.utc)`; avoided `class Config` in favor of `model_config = SettingsConfigDict(...)`.
- **Graceful Loopback Simulation**: When target upstream APIs are mock URLs or offline during tests/local development, `DynamicTenantRouter` captures the `httpx.ConnectError` and simulates upstream delivery without crashing the pipeline, returning structured simulation data.

## 3. Key File Layout
- `main.py`: Root launcher script.
- `src/main.py`: FastAPI application wiring all endpoints and static routes.
- `src/vault/radial_vault.py`: Concentric ring vector vault and secret encryption.
- `src/router/dynamic_router.py`: Token bucket rate limiting and proxy dispatcher.
- `src/db/pool_manager.py`: Multi-tenant DB session manager and audit logger.
- `src/mcp/hooks.py`: MCP tool definitions and AI agent context bridge.
- `src/portal/index.html`: Responsive developer portal UI with HTML5 canvas visualizer.
- `core/`: Tier-1 math engines — `vrl1_algo.py` (integer torus + proof-of-possession),
  `secure_vault.py` (AEAD vault + signed persistence), `transparency.py` (Merkle log),
  plus the legacy float engine in `vector_math.py` / `vault.py`.
- `api/gateway.py`: standalone demo app (`create_app`) + secure app (`create_secure_app`).
- `core/_rust.py`: optional PyO3 import shim (falls back to pure Python when the
  extension is absent). `rust/vrl1_core/`: the Rust crate (build with `maturin`).
- `tests/`: unit + integration tests (75 passing at v1.9.0).

## 4. Tier-1 Security Invariants (v1.2+ / v1.4)
- Coordinates are **static per (tenant, key, epoch)** — the nonce never enters the
  coordinate; it only protects the per-request proof. Exact integer equality only.
- The nonce ledger burns a nonce **only after** full verification, so failed attempts
  cannot poison a victim's nonce. It fails closed when full.
- Records are AEAD-bound to (tenant, radius, shards, epoch, scopes); any move/tamper/
  scope-escalation fails `InvalidTag` organically.
- Secure mode gates enrollment behind an admin key and refuses to run without a
  ≥32-byte master key (unless `demo=True`). Vault persistence signs its transparency
  root, so rollback/forgery is detected on load.
- Capability-attenuated tokens let agents act on a tenant's behalf without the raw
  key; caveats (scope subset, expiry, path prefix, max-use budget) are enforced at
  dispatch. A `*` enrollment scope grants any attenuation.
- A CUSUM circuit breaker fails closed per tenant + per shard: while open, requests
  are rejected before proof/nonce verification, so a brute-force flood never burns
  the victim's nonce ledger. Runtime state only (not persisted).
- The hot-path ledgers (replay nonce + capability usage) are behind protocols
  (`NonceStore`, `CapabilityUsageStore`) with SQLite/WAL, Redis (atomic
  `SET NX EX`/`INCR`, verified via fakeredis), and Postgres (atomic
  `ON CONFLICT`, verified via embedded-postgres) backends.
- Threshold credential release uses Feldman VSS over RFC 3526 group 14 (a
  2048-bit safe prime): t-of-n Shamir shares in GF(Q), commitments C_j = G^{a_j},
  and a share verifies iff G^{f(i)} == prod_j C_j^{i^j} mod P. Multi-node
  distribution/orchestration is Milestone 5 (BFT).
- The Rust core ports `derive_coordinate` / `make_proof` / `spatialize_key` (d=4);
  `core/_rust.py` imports it when built and otherwise falls back to pure Python.
  `proof_key` is cached because it feeds every gateway `verify_request`. Rust
  functions release the GIL (`Python::detach`); at ~2 µs/op the win is ~2×
  single-thread, and parallel scaling is small/noisy (thread overhead dominates).
- Never log raw API keys — fingerprint prefix only. Rejected requests write nothing.
