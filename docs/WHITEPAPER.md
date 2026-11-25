# HyperNexus — Technical Summary

**A zero-trust identity & API control plane for AI agents.**

United Beats LLC · Robert Matthew Pelloni (math/core) · Lumbros Kourlos (systems/interface)

---

## What it is

Two products on one core:

- **VRL-1 (the vault)** — a multi-tenant API gateway that stores keys as *geometric coordinates*, enforces disjoint tenant rings, isolates traffic, and serves AI agents over the Model Context Protocol (MCP).
- **VRL-4 GAP (the key)** — passwordless authentication: a device proves its identity with hardware, a zero-knowledge proof, and a speed-of-light distance check. No password crosses the wire.

They connect through a protocol: GAP proves *who you are*; VRL-1 verifies *what you're allowed to reach*.

## How it works (the math, stated plainly)

- **Key hierarchy** — HKDF-SHA256 from a ≥32-byte master key derives per-tenant, per-proof, and per-record keys.
- **Coordinates** — a key hashes (HMAC-SHA256) to `(r, θ₁, θ₂, θ₃)` as 4 × uint64. Tenants own disjoint rings. Verification uses **exact integer equality — no tolerance, ever**.
- **Records** — routing data is sealed with ChaCha20-Poly1305 AEAD bound to `(tenant, radius, shards, epoch, scopes)`.
- **Replay defense** — a nonce ledger that burns a nonce *only after* full verification; freshness ±120 s.
- **Isolation** — O(1) routing; a cross-tenant request fails at the math layer, before any database or HTTP I/O.
- **Passwordless (VRL-4)** — hardware seed → Reed-Solomon fuzzy extractor → Schnorr zero-knowledge proof → RTT/Kalman/geodesic distance bound.

## What is proven (129 passing tests)

- Stolen coordinate without the key → nothing
- Replay / nonce-poisoning resistance
- Cross-tenant and ring-overlap rejection
- AEAD tamper / move / scope-escalation failures
- Merkle transparency (rollback/deletion detection)
- Capability tokens, CUSUM circuit breaker
- Threshold (Feldman VSS) credential release
- PBFT multi-node consensus (agreement + view-change)
- Schnorr ZK, Reed-Solomon correction, Rust-core parity
- A TLA+ model of the vault invariants, model-checked with TLC

## What is *not* yet proven (stated plainly)

- **Speed-of-light distance** — loopback-validated; real-world (LAN → internet) calibration pending.
- **Hardware root of trust** — TPM detection done; full TPM 2.0 attestation (PCR quote) pending.
- **Independent cryptographic review** — not yet performed. We welcome it.

## Measured

- `derive_coordinate` ≈ 2–8 µs (Rust) vs ~13 µs (pure Python).
- HTTP crucible: VRL-1's full zero-trust path ≈ **2.4× a bare dict lookup** — the honest cost of torus + proof-of-possession + AEAD.

## Status

- **VRL-1** — working MVP: production entrypoint, TLS, key rotation, multi-node consensus.
- **VRL-4** — working prototype: full handshake on loopback.

---

*We'd be honored if someone would look at this and tell us where we're wrong — we'd rather be corrected early than be wrong at scale.*
