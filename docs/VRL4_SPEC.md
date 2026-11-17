# HyperNexus VRL-4 — Geometric Authentication Protocol (GAP) · Technical Specification

**United Beats LLC · UNITEDBEATS.ONLINE · LUMBROS.ME**

> Companion to [README-VRL4.md](../README-VRL4.md). This is the engineering spec:
> the baseline prototype, the four hardening upgrades, the build phases, and
> additional mathematical notes.

---

## 1. Baseline Prototype

The reference gateway performs two checks: a physics/latency gate and an
exact-geometry gate.

```python
import time
import hmac
import hashlib
import numpy as np

class GeometricAuthenticator:
    """
    HyperNexus VRL-4 Passwordless Authentication.
    Validates physical network latency (light speed) and exact torus geometry.
    """
    def __init__(self, expected_latency_ms: float, latency_tolerance: float = 15.0):
        self.expected_latency_ms = expected_latency_ms
        self.latency_tolerance = latency_tolerance

    def verify_physics_and_light(self, client_timestamp: float, arrival_time: float) -> bool:
        actual_latency = (arrival_time - client_timestamp) * 1000  # ms
        if abs(actual_latency - self.expected_latency_ms) > self.latency_tolerance:
            return False
        return True

    def verify_geometric_proof(self, claimed_r, claimed_shards, signature,
                               payload, tenant_min_r, tenant_max_r) -> bool:
        if not (tenant_min_r <= claimed_r < tenant_max_r):
            return False
        coordinate_key = claimed_shards.tobytes()
        expected_sig = hmac.new(coordinate_key, payload, hashlib.sha256).digest()
        return hmac.compare_digest(expected_sig, signature)
```

**Known prototype limitation:** `verify_physics_and_light` trusts the client's
clock (`client_timestamp`), which can be spoofed. The RTT upgrade below removes
that trust.

---

## 2. The Four Hardening Upgrades

### 2.1 The Relativity Fix — Round-Trip Challenge-Response
- Gateway issues a fresh, signed nonce; client signs it with its Torus coordinate.
- Gateway measures `RTT = T_receive − T_send` on its own clock only.
- Removes client-clock (NTP spoofing) as an attack vector.

### 2.2 Fuzzy Extractors — Forgiving Silicon Noise
- PUF output varies with temperature/voltage.
- A Fuzzy Extractor (Reed-Solomon / BCH) + helper data reconstructs the exact
  256-bit secret from a noisy reading, so the integer math stays absolute.

### 2.3 Kalman Filtering — Taming Network Jitter
- Static latency thresholds cause false lockouts under congestion.
- A Kalman Filter learns each device's latency state, adapting to normal jitter
  while rejecting physically impossible spikes (proxies/VPNs).

### 2.4 Geodesic Torus Mapping — Physics on the Globe
- RTT → maximum physical radius (speed of light in fiber, ~200 km/ms round-trip).
- Check against the IP's WGS 84 geolocation to bound the device physically.

---

## 3. Build Phases

1. **Local Loopback** — RTT + torus math on `localhost`. *Warning:* localhost
   latency is sub-millisecond; do not hard-code a minimum, or the gateway will
   reject its own traffic.
2. **LAN Crucible** — separate machine, Fuzzy Extractor, deliberate heat/CPU
   stress to prove noisy hardware still yields the perfect coordinate.
3. **The Wild** — live server, Kalman Filter, mapping the real latency sphere.

---

## 4. Additional Hardening (our notes)

1. **Transcript-bound challenges.** The client's signature must cover the gateway
   nonce *and* the client's own fresh nonce, so a man-in-the-middle cannot relay
   a legitimate signed challenge from elsewhere. Binding to `(ring, epoch, nonce)`
   makes every proof single-use and non-transferable.

2. **Helper-data confidentiality.** A stolen Fuzzy-Extractor helper-data blob must
   not enable PIN enumeration — bind helper data to the device (or encrypt it under
   a device-local key) so it is useless off-device.

3. **Epoch-based freshness, not wall-clock.** Reuse the VRL-1 epoch + a short
   challenge TTL for temporal freshness, so no absolute-time trust is required.

4. **Adversarial noise injection.** Add deterministic, per-tenant jitter so the
   latency gate does not become an oracle that leaks ring boundaries.

5. **Progressive hardening.** Ship the math layer first (exact, verifiable today),
   then add RTT + Fuzzy Extractor + Kalman + geodesic in the three build phases —
   never hard-coding thresholds during local testing.

---

## 5. Honest Status

- **VRL-1 core is real and tested** (integer torus, proof-of-possession, AEAD,
  replay, transparency, capability tokens, CUSUM, shared stores, VSS, KMS, Rust
  core) — 100 passing tests.
- **VRL-4 is specification + prototype.** The physics (PUF) and light (RTT)
  layers are the next build phases; the four upgrades are the roadmap to
  production hardening.

---

**Systems Architecture & UI** — Lumbros Kourlos
**Math Engineering & Core Logic** — Robert Matthew Pelloni
