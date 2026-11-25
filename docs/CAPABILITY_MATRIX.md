# HyperNexus — Product Capability Matrix (VRL-1 & VRL-4)

What is **built & tested** vs. what is **still needed to ship each as a product**.

---

## VRL-1 — The Vault / API Control Plane (the lock)

### Built & tested
- **Integer-torus engine** (`d=4`, 256-bit coordinate, HKDF per-tenant keys, exact equality, no tolerance)
- **Proof-of-possession** HMAC (freshness ±120 s, constant-time compare)
- **Replay ledger** (nonce burned only after full verification, TTL, fail-closed)
- **AEAD records** (ChaCha20-Poly1305 bound to tenant/radius/shards/epoch/scopes)
- **Disjoint-ring tenant registration** (overlap rejected; generated in-ring keys)
- **Admin-gated enrollment** (`VRL1_ADMIN_KEY`, demo key surfaced only in demo)
- **Signed, tamper-evident persistence** (HMAC over transparency root; rollback refused)
- **Merkle transparency log** (inclusion proofs)
- **Capability-attenuated tokens** (scope/expiry/path/max-uses caveats)
- **CUSUM anomaly detection + circuit breaker** (fail-closed, per tenant + shard)
- **Shared stores:** SQLite/WAL, Redis, Postgres (atomic nonce + usage)
- **Feldman VSS** threshold credential release (t-of-n)
- **KMS custody** via Vault (`VaultMasterKeySource`)
- **Rust core** (PyO3) for coordinate/proof derivation + GIL release
- **TLA+ model** of register/persist/reload invariants (TLC-checked)
- **122 tests**, micro + HTTP benchmarks, CI

### Still needed to be a *product*
- [ ] **Production KMS/HSM** — HA Vault or cloud HSM (currently dev-mode)
- [ ] **Multi-node deployment** — wire PBFT/VSS into the actual vault write path (≥4 nodes)
- [ ] **Production shared stores** — real Redis/Postgres clusters, TLS, failover
- [ ] **Independent crypto review + penetration test**
- [ ] **Phase-1 benchmark crucible** — gateway vs Kong/Nginx+Redis @ 10k rps (the O(1)/energy claim stays locked until this)
- [ ] **Operational** — HA, backups, monitoring/alerting, key rotation & ceremony, edge rate-limit/DDoS, TLS
- [ ] **Compliance** — SOC 2 / Common Criteria (process)
- [ ] **Retire/harden legacy `src/` demo path** (hardcoded demo keys)

---

## VRL-4 — GAP / Passwordless Authentication (the key)

### Built & tested
- **Fuzzy extractor** — repetition code (Rust) *and* Reed-Solomon GF(256) codec (production-grade byte-error correction)
- **Schnorr zero-knowledge proof-of-possession** (RFC 3526 group 14) — secret never leaves the device
- **RTT challenge-response** — measured on the gateway's own clock (no client-clock trust)
- **Kalman latency filter** — learns a device's latency sphere, flags impossible spikes
- **WGS 84 geodesic bound** — RTT → max physical radius vs IP location
- **Full handshake** (`GapAuthenticator` + `SchnorrGapAuthenticator`) — physics → light → math
- **Client** — deterministic device fingerprint + loopback demo
- **Real-socket gateway** (`core/vrl4_net.py`) + loopback tests

### Still needed to be a *product*
- [ ] **True hardware entropy** — integrate a real PUF/TPM/secure-enclave (today: deterministic fingerprint)
- [ ] **LAN → live-internet calibration** — real RTT/Kalman/geodesic tuning beyond loopback
- [ ] **Independent review** of the ZK + speed-of-light claims
- [ ] **Production client** — daemon/app, OS keychain/TPM key storage, enrollment UX, device recovery/rotation
- [ ] **Geolocation feed** — a real IP-geolocation source + privacy posture
- [ ] **Multi-device enrollment** — the same identity across devices

---

## The seam (how they connect)

```
Device → [PUF+PIN → fuzzy key → Schnorr sign challenge] → GapProof
        → gateway: verify ZK + RTT/Kalman/geodesic
        → VRL-1: resolve_by_key(public identity) → ring → route/scope
```

GAP is vault-agnostic; VRL-1 is one verifier backend. They are coupled only by the `GapProof` protocol.
