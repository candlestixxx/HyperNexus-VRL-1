"""VRL-4 GAP over a real network socket (loopback demo).

`build_gap_gateway` serves the GAP challenge/prove endpoints with the RTT
measured on the gateway's own clock (no client-clock trust). `gap_client_handshake`
drives the two-step handshake over HTTP and reports the measured round-trip time.

Loopback note: localhost RTT is sub-millisecond. Do NOT hard-code a minimum in
production, or the gateway will reject its own traffic. For the LAN crucible,
run the client on a second machine pointed at this gateway's address.
"""
from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.vrl4_gap import GapAuthenticator, GapChallenge, GapProof


def build_gap_gateway(gap: GapAuthenticator):
    app = FastAPI(title="HyperNexus VRL-4 GAP Gateway")
    app.state.gap = gap
    app.state.pending: dict[str, float] = {}  # nonce_hex -> server send time

    @app.get("/health")
    async def health() -> dict:
        return {"status": "healthy", "mode": "vrl4-gap"}

    @app.get("/gap/challenge")
    async def challenge() -> dict:
        c = gap.issue_challenge()
        app.state.pending[c.nonce.hex()] = time.time()  # own clock, not the client's
        return {"nonce": c.nonce.hex()}

    @app.post("/gap/prove")
    async def prove(request: Request):
        body = await request.json()
        nonce = bytes.fromhex(body["nonce"])
        sent_at = app.state.pending.pop(nonce.hex(), None)
        if sent_at is None:
            return JSONResponse(status_code=403, content={"detail": "unknown challenge"})
        rtt_ms = (time.time() - sent_at) * 1000.0
        proof = GapProof(body["tenant_id"], body["device_id"], nonce,
                         bytes.fromhex(body["client_nonce"]),
                         bytes.fromhex(body["signature"]))
        try:
            out = gap.verify(proof, device_lat=body["lat"], device_lon=body["lon"],
                             rtt_ms=rtt_ms)
        except PermissionError as e:
            return JSONResponse(status_code=403, content={"detail": str(e)})
        return {"status": "access_granted", "rtt_ms": round(rtt_ms, 3),
                "target_url": out["target_url"]}

    return app


def gap_client_handshake(base_url: str, gap: GapAuthenticator, reading: bytes, pin: str,
                         lat: float, lon: float) -> dict:
    import httpx

    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        nonce_hex = client.get("/gap/challenge").json()["nonce"]
        challenge = GapChallenge(bytes.fromhex(nonce_hex), time.time())
        proof = gap.prove(reading, pin, challenge)
        resp = client.post("/gap/prove", json={
            "tenant_id": proof.tenant_id,
            "device_id": proof.device_id,
            "nonce": proof.nonce.hex(),
            "client_nonce": proof.client_nonce.hex(),
            "signature": proof.signature.hex(),
            "lat": lat,
            "lon": lon,
        })
        return resp.json()
