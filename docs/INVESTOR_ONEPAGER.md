# HyperNexus — Zero-Trust Identity & API Control Plane for the AI Agent Era

**United Beats LLC · UNITEDBEATS.ONLINE · LUMBROS.ME**

> One page for investors and partners: what it is, what's proven, and the path forward.

---

## The one-line thesis

**HyperNexus replaces the password and the flat key-value store with a geometric coordinate you can prove** — a zero-trust control plane where API keys and identities live in disjoint mathematical rings, and where an AI agent (or a human, or a device) proves it belongs in a ring using hardware, zero-knowledge proofs, and the laws of physics.

## Two products, one seam

| | **HyperNexus VRL-1** — *the lock* | **HyperNexus VRL-4 GAP** — *the key* |
|---|---|---|
| What it is | Multi-tenant API vault + gateway + agent control plane | Passwordless authentication protocol |
| Job | Store secrets as geometric coordinates; enforce tenant rings; route & isolate traffic; serve MCP agents | Prove "I am this device, at this distance, at this time" — without sending a password or secret |
| Category | API gateway / secrets management / zero-trust | Identity / passwordless / hardware-bound auth |
| Sells on | Isolation, O(1) routing, agent-native control | "The password is dead" — ZK + PUF + speed-of-light |

They connect through a **protocol** (`GapProof`), not shared internals: GAP proves the *identity*, VRL-1 verifies the *authorization*. Each can be sold and shipped independently.

## The core insight

1. **Keys become geography.** Every API key hashes to a point `(r, θ₁, θ₂, θ₃)` on a 4-dimensional integer torus. Tenants own disjoint rings. Routing is `O(1)` in tenant count, and cross-tenant access fails at the math layer — *before* any database or HTTP I/O.
2. **Passwords become proofs.** A device's hardware fingerprint + PIN is fuzzy-extracted into a stable secret *on the device*; the device proves possession with a **Schnorr zero-knowledge signature** (the secret never crosses the wire); the network's **speed-of-light round-trip** is a second factor.
3. **The math is battle-tested.** Under the hood it is HKDF, HMAC-SHA256, ChaCha20-Poly1305 AEAD, replay ledgers, Merkle transparency, threshold secret sharing, and BFT consensus — standard, auditable primitives. The *geometry* is the novel indexing and the story; the *crypto* is conventional strength.

## What is actually proven today

- **122 passing tests** across the full suite: stolen-vector rejection, replay/nonce-poisoning resistance, cross-tenant/ring-overlap rejection, AEAD tamper/move/scope-escalation failures, transparency proofs, capability-token caveats, circuit-breaker fail-closed, threshold VSS, Schnorr ZK, Reed-Solomon correction, and Rust-core parity.
- **Runnable software** on both branches: a FastAPI secure gateway (VRL-1) and a working passwordless handshake (VRL-4) validated on loopback.
- **Formal model** of the vault's register/persist/reload invariants, model-checked with TLC.
- **Micro + HTTP benchmarks** published with honest numbers (Rust core ~2× on primitives; no external performance claim is made without a Kong/Redis baseline).

## Why now

Autonomous AI agents are becoming primary operators of corporate infrastructure, and **agent identity + isolation** is a genuinely underserved, fast-moving problem (Model Context Protocol adoption is accelerating). Passwordless/phishing-resistant auth is simultaneously being forced by regulation and breaches. HyperNexus sits at the intersection of **agent-native control plane** and **hardware-bound passwordless identity** — with a novel, defensible story.

## Market position (honest)

- **Primary peers:** Kong, Apigee, Tyk, AWS API Gateway, Cloudflare Zero Trust, HashiCorp Vault, AWS KMS/Secrets Manager, and passwordless/PUF players (passkeys/WebAuthn, TPM, secure-enclave attestation).
- **Wedge:** *zero-trust identity and isolation for AI agents* — not "we outrun Kong on throughput." We win the narrative on the agent-native + geometric + passwordless combination, and we win on *honesty* (proven limits stated plainly).

## Roadmap

- **Now (short):** validate VRL-4 on LAN → live internet (real RTT/Kalman calibration); land 2–3 agent-security reference deployments; independent crypto + pen review; Kong/Redis benchmark.
- **Mid:** wire BFT/VSS into a real multi-node vault; production KMS (HA Vault / cloud HSM); production Redis/Postgres; SOC 2 program.
- **Long:** a custom-silicon or IP-licensing play (hardware root of trust), building on existing TPM/PUF/secure-enclave silicon rather than self-fabrication.

## Team

- **Robert Matthew Pelloni (Bob)** — Math Engineering & Core Logic.
- **Lumbros Kourlos** — Systems Architecture & Interface.

## Honest status line

VRL-1 is a working, tested **MVP**; VRL-4 is a working, tested **prototype** (loopback-validated). The novel physics claims (speed-of-light distance, true silicon PUF) are *pending real-world validation* and are not yet asserted as fact. See `docs/CAPABILITY_MATRIX.md` for the exact build-to-product gap.
