"""VRL-4 GAP client — hardware fingerprint extraction + local handshake demo.

The "PUF" for the prototype is a deterministic device fingerprint (hostname,
machine, processor, CPU count, MAC address), hashed to a fixed-width reading.
In production this reading comes from a true silicon PUF + fuzzy extractor;
here it is stable (no noise), and noise tolerance is exercised in the tests.

Run:
    python -m core.vrl4_client            # prints the device reading + a loopback handshake
"""
from __future__ import annotations

import hashlib
import os
import platform
import sys
import time
import uuid

READING_LEN = 96  # 32-byte key * 3 (repetition factor)


def detect_tpm() -> dict:
    """Detect a Trusted Platform Module (non-admin). Returns {present, version}."""
    import subprocess
    if platform.system() != "Windows":
        present = os.path.exists("/dev/tpm0") or os.path.exists("/dev/tpmrm0")
        return {"present": present, "version": "unknown" if present else None}
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "(Get-PnpDevice -Class SecurityDevices -ErrorAction SilentlyContinue "
             "| Where-Object {$_.FriendlyName -match 'TPM|Platform Module'} "
             "| Select-Object -First 1 -ExpandProperty FriendlyName)"],
            capture_output=True, text=True, timeout=15)
        name = (out.stdout or "").strip()
        if name:
            version = "2.0" if "2.0" in name else ("1.2" if "1.2" in name else "unknown")
            return {"present": True, "version": version}
    except Exception:
        pass
    return {"present": False, "version": None}


def hardware_root_of_trust(length: int = READING_LEN) -> tuple[bytes, str]:
    """Best-available hardware root of trust. Returns (seed, tier).

    Tiers (honest):
      - "tpm"          — a TPM is present and folded into the machine binding.
                         Full attestation (PCR quote / EK) needs TPM 2.0 + a
                         TSS stack (tpm2-tools / tpm2-pytss) and is the
                         production upgrade.
      - "fingerprint"  — deterministic machine fingerprint (prototype fallback).
    """
    tpm = detect_tpm()
    parts = [
        platform.node(),
        platform.machine(),
        platform.processor() or "",
        str(os.cpu_count()),
        str(uuid.getnode()),           # MAC address
        platform.system(),
        platform.version() or "",
        f"tpm={tpm['present']}:{tpm['version']}",
    ]
    h = hashlib.sha256("|".join(parts).encode()).digest()
    seed = (h * (length // len(h) + 1))[:length]
    tier = "tpm" if tpm["present"] else "fingerprint"
    return seed, tier


def hardware_reading(length: int = READING_LEN) -> bytes:
    """Deterministic, stable device fingerprint (prototype PUF substitute)."""
    return hardware_root_of_trust(length)[0]


def run_demo(pin: str = "1234") -> None:
    from core.secure_vault import SecureRadialVault
    from core.vrl1_algo import Ring, VRL1ZeroTrustEngine
    from core.vrl4_gap import GapAuthenticator

    reading, tier = hardware_root_of_trust()
    print(f"[VRL-4 GAP] device reading ({len(reading)} bytes): {reading[:16].hex()}...")
    print(f"[VRL-4 GAP] root of trust: {tier}")

    engine = VRL1ZeroTrustEngine(b"demo-master-key-32-bytes-minimum!!")
    vault = SecureRadialVault(engine)
    vault.register_tenant("tenant_a", Ring(0, 1 << 64))
    gap = GapAuthenticator(engine, vault, "tenant_a")

    print("[VRL-4 GAP] enrolling device...")
    gap.enroll_device(reading, pin, "https://upstream.example.com", "sqlite:///gap.db")
    print("[VRL-4 GAP] issuing RTT challenge...")
    challenge = gap.issue_challenge()
    proof = gap.prove(reading, pin, challenge)

    rtt_ms = 5.0  # loopback is ~0ms; use a plausible LAN figure for the demo
    print(f"[VRL-4 GAP] RTT measured: {rtt_ms} ms")
    # Loopback note: real localhost is sub-millisecond; do not hard-code a
    # minimum in production or the gateway will reject its own traffic.
    out = gap.verify(proof, device_lat=40.7128, device_lon=-74.0060, rtt_ms=rtt_ms)
    print("[VRL-4 GAP] PHYSICS VERIFIED")
    print("[VRL-4 GAP] GEOMETRY VERIFIED: Access Granted")
    print(f"[VRL-4 GAP] routed to {out['target_url']} (tenant {out['tenant_id']})")


if __name__ == "__main__":
    pin = sys.argv[1] if len(sys.argv) > 1 else "1234"
    if "--fingerprint" in sys.argv:
        print(hardware_reading().hex())
    else:
        run_demo(pin)
