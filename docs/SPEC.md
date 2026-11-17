# VRL-1 Tier-1 Parameter Spec (locked) + Audit/Market Readiness

Implementation: [core/vrl1_algo.py](../core/vrl1_algo.py), [core/secure_vault.py](../core/secure_vault.py) · Tests: [tests/test_vrl1_algo.py](../tests/test_vrl1_algo.py)

| Parameter | Locked value |
|---|---|
| Dimension | `d = 4` (1 radius word + 3 shard words, uint64 each, big-endian) |
| Match rule | Exact integer equality. No tolerance anywhere on the auth path |
| Coordinate | `HMAC-SHA256(HKDF(K_master, tenant), canon(tenant, key, epoch))` — static per epoch, nonce never included |
| Request proof | `HMAC(proof_key, canon(nonce, ts, method, path, SHA256(body)))`, constant-time compare, ±120 s window |
| Replay | Tenant-scoped nonce ledger; nonce burned **only after** full verification; TTL expiry; fail-closed when full |
| Rings | Disjoint uint64 intervals, overlap rejected at registration; radius is *checked*, never projected |
| Enrollment | System-generated 256-bit CSPRNG keys, rejection-sampled into the ring; BYO keys deriving out-of-ring are refused |
| Collisions | Shard collision at enrollment = hard panic (`ShardCollisionPanic`) |
| Records | ChaCha20-Poly1305 AEAD, AAD = canon(tenant, radius, shards, epoch, scopes); moved/tampered/escalated records fail `InvalidTag` |
| Rotation | Dual-read epochs `e` and `e−1`, then old epoch dropped |

## Pitch wording (defensible — use this, not "physically impossible")
> Cross-tenant access fails through every exposed code path. Credentials are never accepted on coordinate knowledge alone — every request must prove key possession, freshness, and exact in-ring shard match. Tampering with a record's ring, shard, epoch, or scope fails AEAD authentication organically.

## Measured (dev laptop, Python, single core)
`derive_coordinate` ≈ 7.5 µs/op (~133k derivations/s/core) vs 0.13 µs for a raw dict lookup. Honest reading: negligible next to network/DB latency, ~56× a bare lookup — the gap the Rust port closes. Full gateway-vs-baseline benchmark still owed (ROADMAP Phase 1).

## Audit readiness — what exists vs what an audit still requires
Exists: locked spec, exact-match math, tamper-evident records, replay/freshness, Merkle transparency log, capability-attenuated tokens, CUSUM circuit breaker, shared-store interfaces, Feldman VSS threshold release, 70 passing tests incl. stolen-vector, collision-panic, and tamper-detection cases.
Still required before claiming "audit-passed": KMS/HSM key custody, multi-node consensus (BFT) for ring state, independent penetration test, SOC 2 / Common Criteria process controls. No honest vendor passes a defense audit on code alone — budget for the process, not just the protocol.

## Scale & market path
Scale: stateless engines scale horizontally once the nonce ledger and vault move to shared stores (Redis/Postgres) behind the same interfaces; BFT consensus is the gate for multi-writer ring state.
Market: open-source core → published benchmarks → 10 design-partner deployments (agent-heavy mid-size firms) → enterprise tier (threshold release, transparency log, support). Licensing talks with platform vendors are a *consequence* of adoption metrics, not an entry strategy.
