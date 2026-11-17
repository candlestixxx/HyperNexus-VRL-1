# Long-Term Structural Roadmap — HyperNexus VRL-1

## Done
- [x] v1.0.0 `src/` gateway: portal UI, Fernet radial vault, dynamic router, DB audit pools, MCP JSON-RPC (18 tests)
- [x] v1.1.0 float radial math core (`core/vector_math.py`, `core/vault.py`), standalone dispatch gateway (28 tests)
- [x] v1.2.0 Tier-1 integer-torus engine: HKDF tenant keys, proof-of-possession, AEAD vault, replay ledger (35 tests) — [docs/SPEC.md](docs/SPEC.md)

## Milestone 3: Secure Gateway Integration (v1.3.x — shipped)
- [x] Wire `SecureRadialVault` into `api/gateway.py` (proof headers, 403 drop, no demo vault on secure path)
- [x] Merkle transparency log over vault enrollments (rollback/deletion detection)
- [x] Property-based invariant fuzzing (ring disjointness, cross-tenant rejection at scale)
- [x] Single version source: app reads `VERSION.md`, no hardcoded versions
- [x] Gateway-vs-baseline benchmark harness + published results in `docs/BENCHMARKS.md`
- [x] GitHub Actions CI running the full suite on push

## Milestone 4: Enterprise Tier (v1.4.x)
- [x] Threshold (Feldman VSS) credential release; no whole secrets on one node
- [x] Env-required secrets, no shipped defaults (secure mode refuses demo keys unless `demo=True`; `VRL1_MASTER_KEY` + `VRL1_ADMIN_KEY` required)
- [ ] KMS/HSM master-key custody (external service integration)
- [x] Signed tamper-evident vault persistence (rollback/deletion detection at rest)
- [x] Capability-attenuated MCP agent tokens (scope/expiry/path/max-uses caveats)
- [x] CUSUM anomaly detection + circuit breaker per shard (fail-closed brute-force defense)
- [x] Shared-store interfaces (nonce + capability usage) with SQLite/WAL backend
- [x] Redis drivers (`RedisNonceStore`, `RedisCapabilityUsageStore`) verified via fakeredis
- [x] Postgres driver (`PostgresNonceStore`, `PostgresCapabilityUsageStore`) verified via embedded-postgres

## Milestone 5: Research Tier (v2.x)
- [x] Rust core port (PyO3): `derive_coordinate`, `make_proof`, `spatialize_key` (~2×); `verify_request` orchestration stays in Python
- [ ] ZK ring-membership: field-native commitment (Poseidon-class) designed with the circuit — not a hash swap
- [ ] BFT consensus for multi-writer ring state
- [ ] TLA+ model of register/persist/reload invariants + independent penetration test

## Explicitly not promised
Passing a named audit (SOC 2, Common Criteria) is a process outcome, not a code feature. Open-source adoption and published benchmarks precede any platform licensing conversation.
