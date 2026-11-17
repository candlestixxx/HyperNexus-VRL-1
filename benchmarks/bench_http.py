"""End-to-end HTTP gateway benchmark (in-process ASGI, mock upstream).

Run: python benchmarks/bench_http.py

Measures secure-gateway dispatch throughput + latency under concurrency with
the Rust core enabled vs the pure-Python fallback, so the HTTP-level impact of
the Rust port (and its GIL release) is visible. A Kong/Nginx+Redis baseline
comparison remains the outstanding Phase-1 crucible.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from api.gateway import create_secure_app
from core import _rust

MASTER = b"bench-master-key-32-bytes-minimum!!"
ADMIN = "bench-admin"
TENANT = "tenant_a"
N = 2_000
CONCURRENCY = 8


def _build_app():
    async def upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    return create_secure_app(master_key=MASTER, admin_key=ADMIN,
                             transport=httpx.MockTransport(upstream))


async def _enroll(app) -> str:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://bench") as c:
        r = await c.post("/secure/enroll", headers={"X-VRL1-Admin-Key": ADMIN}, json={
            "tenant_id": TENANT, "target_url": "https://upstream.local",
            "db_connection_string": "sqlite:///bench.db", "scopes": ["*"]})
        r.raise_for_status()
        return r.json()["api_key"]


async def _run(app, key: str, n: int, concurrency: int) -> tuple[float, int, list[float]]:
    engine = app.state.engine
    transport = httpx.ASGITransport(app=app)
    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []

    async def one(i: int):
        nonce = f"bench-{i}"
        ts = int(time.time())
        body = b'{"x":1}'
        proof = engine.make_proof(TENANT, key, nonce, ts, "POST", "/mcp/dispatch/leads", body)
        async with sem:
            start = time.perf_counter()
            async with httpx.AsyncClient(transport=transport, base_url="http://bench") as c:
                r = await c.post("/mcp/dispatch/leads", content=body, headers={
                    "X-API-Key": key, "X-VRL1-Tenant": TENANT, "X-VRL1-Epoch": "1",
                    "X-VRL1-Nonce": nonce, "X-VRL1-Timestamp": str(ts),
                    "X-VRL1-Proof": proof, "Content-Type": "application/json"})
            latencies.append((time.perf_counter() - start) * 1e6)
            return r.status_code

    t0 = time.perf_counter()
    statuses = await asyncio.gather(*[one(i) for i in range(n)])
    dt = time.perf_counter() - t0
    ok = sum(1 for s in statuses if s == 200)
    return dt, ok, latencies


def _pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def _scenario(label: str, rust_enabled: bool) -> None:
    _rust.RUST_AVAILABLE = rust_enabled
    app = _build_app()
    key = asyncio.run(_enroll(app))
    dt, ok, lat = asyncio.run(_run(app, key, N, CONCURRENCY))
    rps = N / dt
    print(f"{label:<18} {rps:10,.0f} req/s | p50 {_pct(lat, .50):7.0f} us | "
          f"p95 {_pct(lat, .95):7.0f} us | 200s {ok}/{N}")


def main() -> None:
    print(f"requests={N} concurrency={CONCURRENCY} rust_built={_rust.RUST_AVAILABLE}")
    _scenario("rust core", True)
    _scenario("pure python", False)


if __name__ == "__main__":
    main()
