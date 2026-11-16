# HyperNexus VRL-1 — The Three Proofs (as implemented)

Code: [core/vector_math.py](../core/vector_math.py) · Tests: [tests/test_zero_trust.py](../tests/test_zero_trust.py)

## Proof I — Spatilization: `f(K) -> (r, θ₁…θ_{d-1})`

Let `h = SHA-256(K)` (32 bytes). Split: `h_tenant = h[0:8]`, `h_payload = h[8:32]`.

- Radius: `r = W · (1 + int(h_tenant) / (2⁶⁴ − 1))`, so `r ∈ [W, 2W)` for ring width `W`.
- Angles: `h_payload` is cut into `d−1` equal chunks; each chunk scales to `θᵢ ∈ [0, 2π)`.

Deterministic: the same key always lands on the same coordinate. The key *is* the address — no key table is consulted to find the shard.

## Proof II — Absolute boundary: disjoint rings

Tenant A owns `[r_A,min, r_A,max)`, Tenant B owns `[r_B,min, r_B,max)`, registered rings must satisfy `D_A ∩ D_B = ∅` (`RadialVault.register_tenant` rejects overlaps).

`route_payload` grants access iff `r_query ∈ [r_min, r_max)` **and** every angular axis matches within tolerance. A vector from ring B fails ring A's radial gate regardless of its angles — rejection happens in the math layer, before HTTP or DB access (proven by `test_cross_tenant_vector_rejected`, `test_radial_gate_rejects_out_of_ring_even_with_perfect_angles`).

## Proof III — O(1) routing in tenant count N

`route_payload(query_r, query_angles, r_min, r_max, target_angles)` takes no tenant collection: one radial comparison chain + `d−1` angular differences, `d` fixed at construction. Cost is independent of N. The vault indexes endpoints by quantized angular shard (dict lookup), so resolution is O(1) expected time as well.

## Honest limits (read before pitching)

- This is **software geometry**, not physics: a compromised process with raw memory access can read any tenant's data. The rings make cross-tenant access fail *through the gateway's only code path*, and make that failure cheap and early. Pair with the envelope encryption in `src/vault/` and per-tenant DB pools — defense in depth, not a single magic wall.
- SHA-256 in Python/NumPy is a prototype. No benchmark vs. Kong/Nginx+Redis exists yet; O(1)-in-N is proven by construction and signature, latency/energy claims still need the Phase-1 benchmark crucible (see [ROADMAP.md](../ROADMAP.md)).
- The production core should be ported to Rust/Go before any "hardware-level speed" claim is made to a partner.
