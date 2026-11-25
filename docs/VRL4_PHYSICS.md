# VRL-4 Physics Primer — Why the Speed of Light Is a Trust Anchor

Companion to [VRL4_SPEC.md](VRL4_SPEC.md). This is the physical foundation for
VRL-4's **Light Layer**: why the speed of light is a legitimate, unspoofable
measure, and how it is already the "fixed ruler" behind GPS, fiber, radar, and
chip design.

---

## 1. Maxwell: electricity + magnetism = the speed of light

James Clerk Maxwell showed that light is an electromagnetic wave — oscillating
electric and magnetic fields regenerating each other as they move. Maxwell's
equations connect the wave speed `c` to two properties of empty space:

```
        c = 1 / sqrt(ε₀ μ₀)
```

- **ε₀ (vacuum permittivity)** — how strongly a vacuum supports electric fields.
- **μ₀ (vacuum permeability)** — how strongly a vacuum supports magnetic fields.

`c = 299,792,458 m/s` (~300,000 km/s, ~186,282 mi/s). It is the **same for every
electromagnetic wave** — radio, microwave, infrared, visible light, UV, X-ray,
gamma — and it is independent of frequency (`c = fλ`).

> The deep point: `c` is not really a property of *light*; it is a property of
> **empty space**. Nothing — no signal, no object — can exceed it, and it is the
> same in every reference frame. That is why it is a trust anchor a clock can't
> lie about.

## 2. Slower in materials — the fiber factor

Passing through glass/water/air slows the wave because atoms interact with the
fields. In optical fiber the refractive index is `n ≈ 1.47`, so light travels at
roughly **two-thirds of vacuum speed**:

```
v = c / n ≈ 204,000 km/s ≈ 200 km/ms  (one way)
```

This `≈200 km/ms` is the conservative constant VRL-4 uses (`SPEED_KM_PER_MS`),
so a measured round-trip time bounds the physical distance:

```
max_distance = (RTT × v) / 2
```

## 3. It is already the fixed ruler of the modern world

- **GPS** — satellites stamp timestamps; the receiver multiplies arrival delay by `c` to fix its position.
- **Fiber internet** — undersea/underground lasers carry the global internet at ~2/3 `c`.
- **Radar / LiDAR** — measure the return time of a bounced pulse to map surroundings.
- **Chip design** — signals move ~5–6 in/ns in silicon/copper; at 3–5 GHz a signal crosses only ~1–2 in per tick. The "light-foot bottleneck" is why transistors are packed tight and caches sit next to cores.

## 4. How VRL-4 uses it: distance bounding

VRL-4's Light Layer is **distance bounding** — the same technique used by
keyless cars and HSMs:

1. The gateway issues a challenge and timestamps it on **its own clock**.
2. The client responds; the gateway measures `RTT = T_receive − T_send`.
3. Because nothing beats `c`, the RTT puts a **hard upper bound** on distance.
4. A stolen credential replayed through a proxy on another continent arrives
   too late → **rejected by physics, not by policy**.

The **Kalman filter** is what makes this survive the real internet: measured
latency is dominated by queueing/routing jitter, so the filter learns each
device's "latency sphere" and only rejects *impossible* spikes.

## 5. The security context (and the hardware path)

The industry already secures hardware with electromagnetic physics — this is
where a future custom-silicon/HSM play lands:

- **Faraday cages / shielding** — block the EM side-channel that leaks key bits during computation.
- **Tamper-response meshes** — an energized wire grid that, if drilled, breaks the circuit at near-light speed and wipes the keys.
- **Quantum Key Distribution (QKD)** — single photons in fiber; an eavesdropper can't measure without disturbing the state.
- **NFC / proximity tokens** — EM induction only works within a few cm, enforcing physical presence.

VRL-4's software already performs the *distance-bounding* piece; the side-channel
defense, tamper mesh, and silicon root of trust are the hardware end-state.

## 6. Honest limits

- **One-directional.** The check catches "too far away" (remote replay/proxy); it does *not* catch an attacker physically beside you, or a stolen device + PIN.
- **Jitter-dominated.** Measured latency is queueing, not `c`; hence the Kalman tolerance.
- **Authentication, not encryption.** The light layer proves *where*; AEAD + threshold VSS protect the *data*.

> **The math encrypts, the geometry isolates, and the speed of light authenticates.**
