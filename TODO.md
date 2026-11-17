# Granular Short-Term Tasks — HyperNexus VRL-1

P1–P8 shipped in v1.3.0. v1.4.0 added admin-gated enrollment + signed tamper-evident
vault persistence. Remaining work is Milestone 4 (Enterprise Tier), broken into
single-cycle tasks below — highest priority first.

## Next (in order)
- [x] **Capability-attenuated MCP agent tokens** — signed, caveated tokens (scopes, expiry, path prefix, max uses) minted with the admin key and enforced on the secure dispatch path. *Rationale: closes the "agent holds a full API key" gap before CUSUM/shared stores.*
- [ ] **CUSUM anomaly detection + per-shard circuit breaker** — detect auth-failure spikes and trip a breaker that rejects a shard without burning its nonce ledger. *Rationale: fail-closed under brute-force before an attacker can exhaust the replay ledger.*
- [ ] **Shared-store interfaces (Redis/Postgres)** behind `NonceLedger` + vault persistence backends. *Rationale: horizontal-scale prerequisite; the stateless engine already separates these behind narrow interfaces.*

## Blocked / external
- [ ] **KMS/HSM master-key custody** — external service integration; the env-required portion is done. *Blocked on infra choice.*

## Research tier (v2.x — NOT short-term; see ROADMAP Milestone 5)
- Rust core port (PyO3), ZK ring-membership (field-native commitment), BFT consensus, TLA+ model.
