"""
HyperNexus VRL-1 — Async MCP Gateway.

POST /mcp/dispatch/{path:path}
  1. Reads X-API-Key, resolves it through RadialVault (math layer first).
  2. Unauthorized -> 403 immediately. Nothing is written to any DB/log store
     for rejected keys (prevents log-poisoning / audit flooding).
  3. Authorized -> forwards the JSON body upstream with httpx.AsyncClient.

Run:  uvicorn api.gateway:app --host 0.0.0.0 --port 8001
"""
from __future__ import annotations

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from core.vault import RadialVault, RadialVaultUnauthorized

_FORWARD_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def create_app(vault: RadialVault | None = None,
               transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """App factory; `transport` lets tests inject an in-process upstream."""
    vault = vault or _demo_vault()
    app = FastAPI(title="HyperNexus VRL-1 Gateway", version="1.1.0")
    app.state.vault = vault

    @app.get("/health")
    async def health() -> dict:
        return {"status": "healthy", "tenants": vault.list_tenants()}

    @app.api_route("/mcp/dispatch/{path:path}", methods=sorted(_FORWARD_METHODS))
    async def dispatch(path: str, request: Request,
                       x_api_key: str | None = Header(default=None)):
        if not x_api_key:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        try:
            target = vault.resolve_endpoint(x_api_key)
        except RadialVaultUnauthorized:
            # Drop at the math layer. Deliberately no DB write / audit log here.
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

        body = await request.body()
        url = f"{target['target_url']}/{path}" if path else target["target_url"]
        headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in {"host", "x-api-key", "content-length"}}
        try:
            async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
                upstream = await client.request(
                    request.method, url, content=body or None, headers=headers,
                    params=dict(request.query_params))
        except httpx.HTTPError:
            return JSONResponse(status_code=502,
                                content={"detail": "Bad gateway: upstream unreachable"})
        try:
            payload = upstream.json()
        except ValueError:
            payload = {"upstream_text": upstream.text}
        return JSONResponse(status_code=upstream.status_code, content={
            "tenant_id": target["tenant_id"],
            "target_url": url,
            "upstream_status": upstream.status_code,
            "upstream_response": payload,
        })

    return app


def _demo_vault() -> RadialVault:
    """Demo tenants so the gateway runs standalone (replace in production)."""
    v = RadialVault()
    v.register_tenant("tenant_a", 100.0, 200.0)
    v.register_tenant("tenant_b", 300.0, 400.0)
    v.store_endpoint("demo_key_tenant_a_001", "https://api-a.example.com",
                     "sqlite:///data/tenant_a.sqlite3", tenant_id="tenant_a")
    v.store_endpoint("demo_key_tenant_b_001", "https://api-b.example.com",
                     "sqlite:///data/tenant_b.sqlite3", tenant_id="tenant_b")
    return v


app = create_app()
