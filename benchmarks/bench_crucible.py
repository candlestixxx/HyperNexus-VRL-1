"""Credibility-gate benchmark: VRL-1 secure gateway vs bare-lookup baseline.

Runs both under identical load (in-process ASGI + mock upstream) and reports
throughput + p50/p95. The baseline is a plain dict key->route gateway — the
Redis/Kong-class "bare lookup" proxy. This quantifies what VRL-1's full
security (torus + proof-of-possession + AEAD) costs vs a bare lookup.

The real Kong/Nginx+Redis baseline is documented in deploy/ (needs Linux/WSL);
run `bash benchmarks/run_crucible_linux.sh` there.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from api.gateway import create_secure_app

MASTER = b"bench-master-key-32-bytes-minimum!!"
ADMIN = "bench-admin"
KEY = "bench-tenant-key"
N = 2_000
CONCURRENCY = 8


def _build_baseline_app() -> FastAPI:
    routes = {KEY: "tenant_a"}  # bare dict: what Redis/Kong do

    app = FastAPI(title="bare-lookup baseline")

    @app.api_route("/dispatch/{path:path}", methods=["POST", "GET", "PUT", "DELETE", "PATCH"])
    async def dispatch(path: str, request: Request, x_api_key: str | None = Header(default=None)):
        target = routes.get(x_api_key or "")
        if target is None:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return JSONResponse(status_code=200, content={"tenant_id": target, "ok": True})

    return app


def _build_vrl1_app() -> FastAPI:
    async def upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    app = create_secure_app(master_key=MASTER, admin_key=ADMIN,
                            transport=httpx.MockTransport(upstream))
    # Enroll one tenant key (rejection-sampled in-ring) for the client to present.
    key, _ = app.state.vault.enroll_generated_key(
        "tenant_a", 1, "https://upstream.local", "sqlite:///bench.db", scopes=["*"])
    app.state.bench_key = key
    return app


async def _baseline_req(_app, transport, _i):
    async with httpx.AsyncClient(transport=transport, base_url="http://b") as c:
        r = await c.post("/dispatch/leads", headers={"X-API-Key": KEY}, json={"x": 1})
    return r.status_code


async def _vrl1_req(app, transport, i):
    nonce = f"crucible-{i}"
    ts = int(time.time())
    body = b'{"x":1}'
    proof = app.state.engine.make_proof("tenant_a", app.state.bench_key, nonce, ts,
                                        "POST", "/mcp/dispatch/leads", body)
    async with httpx.AsyncClient(transport=transport, base_url="http://v") as c:
        r = await c.post("/mcp/dispatch/leads", content=body, headers={
            "X-API-Key": app.state.bench_key, "X-VRL1-Tenant": "tenant_a", "X-VRL1-Epoch": "1",
            "X-VRL1-Nonce": nonce, "X-VRL1-Timestamp": str(ts),
            "X-VRL1-Proof": proof, "Content-Type": "application/json"})
    return r.status_code


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


async def _run(app, req_fn, n, concurrency):
    transport = httpx.ASGITransport(app=app)
    sem = asyncio.Semaphore(concurrency)
    lat = []

    async def one(i):
        async with sem:
            start = time.perf_counter()
            status = await req_fn(app, transport, i)
            lat.append((time.perf_counter() - start) * 1e6)
            return status

    t0 = time.perf_counter()
    results = await asyncio.gather(*[one(i) for i in range(n)])
    dt = time.perf_counter() - t0
    return n / dt, sum(1 for s in results if s == 200), lat


def main() -> None:
    print(f"requests={N} concurrency={CONCURRENCY}")
    baseline = _build_baseline_app()
    rps_b, ok_b, lat_b = asyncio.run(_run(baseline, _baseline_req, N, CONCURRENCY))
    vrl1 = _build_vrl1_app()
    rps_v, ok_v, lat_v = asyncio.run(_run(vrl1, _vrl1_req, N, CONCURRENCY))
    print(f"{'gateway':<22} {'req/s':>10} {'p50 us':>10} {'p95 us':>10} {'200s':>8}")
    print(f"{'bare lookup':<22} {rps_b:>10,.0f} {_pct(lat_b, .5):>10.0f} {_pct(lat_b, .95):>10.0f} {ok_b:>8}")
    print(f"{'VRL-1 secure':<22} {rps_v:>10,.0f} {_pct(lat_v, .5):>10.0f} {_pct(lat_v, .95):>10.0f} {ok_v:>8}")
    print(f"overhead: VRL-1 is {rps_b / rps_v:.1f}x slower than a bare dict lookup "
          f"(the cost of torus + proof-of-possession + AEAD)")


if __name__ == "__main__":
    main()
