# Granular Short-Term Tasks — HyperNexus VRL-1

P1–P8 shipped in v1.3.0. v1.4.0 added admin-gated enrollment + signed tamper-evident
vault persistence. Remaining work is Milestone 4 (Enterprise Tier), broken into
single-cycle tasks below — highest priority first.

## Next (in order)
- [x] **Capability-attenuated MCP agent tokens** — signed, caveated tokens (scopes, expiry, path prefix, max uses) minted with the admin key and enforced on the secure dispatch path. *Rationale: closes the "agent holds a full API key" gap before CUSUM/shared stores.*
- [x] **CUSUM anomaly detection + per-shard circuit breaker** — detect auth-failure spikes and trip a breaker that rejects a shard without burning its nonce ledger. *Rationale: fail-closed under brute-force before an attacker can exhaust the replay ledger.*
- [x] **Shared-store interfaces (SQLite/WAL)** behind `NonceLedger` + capability-usage backends; Redis/Postgres drivers plug in via the same protocols. *Rationale: horizontal-scale prerequisite; the stateless engine already separates these behind narrow interfaces.*
- [x] **Redis drivers** (`RedisNonceStore`, `RedisCapabilityUsageStore`) verified via `fakeredis`.
- [ ] **Postgres concrete driver** implementing the same `NonceStore` / `CapabilityUsageStore` protocols. *Blocked on a live Postgres to verify; the interface is in place.*

## Blocked / external
- [ ] **KMS/HSM master-key custody** — external service integration; the env-required portion is done. *Blocked on infra choice.*

## Next (in code)
- [x] **Threshold (Feldman VSS) credential release** — `core/threshold.py`: t-of-n Shamir shares with Feldman commitments + share verification + reconstruction, so no single node holds a whole credential. *Rationale: the last Milestone-4 code item before multi-node/BFT (Milestone 5).*

## Research tier (v2.x — NOT short-term; see ROADMAP Milestone 5)
- [x] Rust core port (PyO3): `derive_coordinate` / `make_proof` / `spatialize_key` (~2× measured).
- [ ] ZK ring-membership (field-native commitment), BFT consensus, TLA+ model.
