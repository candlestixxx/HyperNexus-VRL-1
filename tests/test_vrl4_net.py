"""VRL-4 GAP over a real socket: loopback RTT handshake."""
import socket
import threading
import time

import pytest

import uvicorn

from core.secure_vault import SecureRadialVault
from core.vrl1_algo import Ring, VRL1ZeroTrustEngine
from core.vrl4_gap import GapAuthenticator
from core.vrl4_net import build_gap_gateway, gap_client_handshake

MASTER = b"test-master-key-32-bytes-minimum!!"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _serve(app, port: int) -> None:
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")


def _wait_ready(port: int) -> None:
    import httpx
    for _ in range(60):
        try:
            httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.5)
            return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("gateway did not become ready")


def test_real_socket_rtt_handshake():
    engine = VRL1ZeroTrustEngine(MASTER)
    vault = SecureRadialVault(engine)
    vault.register_tenant("tenant_a", Ring(0, 1 << 64))
    gap = GapAuthenticator(engine, vault, "tenant_a")
    reading = b"\x88" * 96
    gap.enroll_device(reading, "1234", "https://a.example.com", "sqlite:///a.db")

    app = build_gap_gateway(gap)
    port = _free_port()
    threading.Thread(target=_serve, args=(app, port), daemon=True).start()
    _wait_ready(port)

    result = gap_client_handshake(f"http://127.0.0.1:{port}", gap, reading, "1234",
                                  40.7128, -74.0060)
    assert result["status"] == "access_granted"
    assert result["rtt_ms"] >= 0.0  # real, positive, sub-ms on loopback
    assert result["target_url"] == "https://a.example.com"


def test_real_socket_rejects_tampered_signature():
    engine = VRL1ZeroTrustEngine(MASTER)
    vault = SecureRadialVault(engine)
    vault.register_tenant("tenant_a", Ring(0, 1 << 64))
    gap = GapAuthenticator(engine, vault, "tenant_a")
    reading = b"\x99" * 96
    gap.enroll_device(reading, "1234", "https://a.example.com", "sqlite:///a.db")

    app = build_gap_gateway(gap)
    port = _free_port()
    threading.Thread(target=_serve, args=(app, port), daemon=True).start()
    _wait_ready(port)

    # Tamper the challenge nonce so the signature does not match.
    import httpx
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10.0) as c:
        nonce_hex = c.get("/gap/challenge").json()["nonce"]
        from core.vrl4_gap import GapChallenge
        challenge = GapChallenge(bytes.fromhex(nonce_hex), time.time())
        proof = gap.prove(reading, "1234", challenge)
        resp = c.post("/gap/prove", json={
            "tenant_id": proof.tenant_id, "device_id": proof.device_id,
            "nonce": proof.nonce.hex(), "client_nonce": proof.client_nonce.hex(),
            "signature": "00" * 32,  # tampered
            "lat": 40.7128, "lon": -74.0060,
        })
    assert resp.status_code == 403
