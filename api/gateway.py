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
import time
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


# ---------------------------------------------------------------------------
# Secure mode (Tier-1): SecureRadialVault + proof-of-possession headers.
# The demo create_app above is unchanged for local exploration; secure mode
# refuses to start without VRL1_MASTER_KEY unless demo=True is explicit.
# ---------------------------------------------------------------------------
import os as _os
import sys as _sys

from fastapi.responses import HTMLResponse as _HTMLResponse
from pydantic import BaseModel as _BaseModel

from core.secure_vault import SecureRadialVault
from core.vrl1_algo import Ring, VRL1ZeroTrustEngine
from vrl1_version import app_version as _app_version

_DEMO_MASTER = b"demo-master-key-not-for-production!!"


class _EnrollRequest(_BaseModel):
    tenant_id: str
    target_url: str
    db_connection_string: str
    scopes: list[str] = ["*"]


class _MintRequest(_BaseModel):
    tenant_id: str
    scopes: list[str]
    exp_seconds: int = 3600
    path_prefix: str = ""
    max_uses: int = 0


def create_secure_app(master_key: bytes | None = None, demo: bool = False,
                      transport: httpx.AsyncBaseTransport | None = None,
                      current_epoch: int = 1, admin_key: str | None = None,
                      persistence_path: str | None = None) -> FastAPI:
    if master_key is None:
        env_key = _os.environ.get("VRL1_MASTER_KEY", "")
        if env_key:
            master_key = env_key.encode()
        elif demo:
            master_key = _DEMO_MASTER
        else:
            raise RuntimeError("VRL1_MASTER_KEY env (>=32 bytes) required, or demo=True")
    # Admin key gates enrollment. Resolution: arg > env > demo-generated.
    import hmac as _hmac
    import secrets as _secrets
    admin_autogenerated = False
    resolved_admin = admin_key or _os.environ.get("VRL1_ADMIN_KEY", "")
    if not resolved_admin:
        if demo:
            resolved_admin = _secrets.token_urlsafe(24)
            admin_autogenerated = True
            # Demo mode only: surface the generated key so /secure/ui and a CLI
            # user can actually enroll. Never printed outside explicit demo mode.
            print(f"[VRL1 secure demo] admin key: {resolved_admin}", file=_sys.stderr)
        else:
            raise RuntimeError("VRL1_ADMIN_KEY env required for enrollment, or demo=True")
    engine = VRL1ZeroTrustEngine(master_key)
    vault = SecureRadialVault(engine, persistence_path=persistence_path)
    if not vault.has_tenant("tenant_a"):
        vault.register_tenant("tenant_a", Ring(0, 1 << 63))
    if not vault.has_tenant("tenant_b"):
        vault.register_tenant("tenant_b", Ring(1 << 63, 1 << 64))
    sapp = FastAPI(title="HyperNexus VRL-1 Secure Gateway", version=_app_version())
    sapp.state.vault = vault
    sapp.state.engine = engine
    sapp.state.current_epoch = current_epoch
    sapp.state.admin_key = resolved_admin  # demo UIs/tests read it here; never via HTTP
    sapp.state.admin_autogenerated = admin_autogenerated

    @sapp.get("/health")
    async def shealth() -> dict:
        return {"status": "healthy", "mode": "secure",
                "transparency_root": vault.transparency_root(),
                "transparency_signature": vault.transparency_signature(),
                "persisted": persistence_path is not None}

    @sapp.get("/secure/ui", response_class=_HTMLResponse)
    async def secure_ui() -> str:
        return _SECURE_UI_HTML

    @sapp.get("/secure/demo-admin-key")
    async def demo_admin_key() -> dict:
        # Exposed ONLY when demo mode auto-generated the key. Real mode (explicit
        # or env key) always hides it: the admin key must never leak over HTTP.
        if not admin_autogenerated:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return {"admin_key": resolved_admin}

    @sapp.post("/secure/enroll")
    async def enroll(req: _EnrollRequest, request: Request):
        supplied = request.headers.get("x-vrl1-admin-key", "")
        if not _hmac.compare_digest(supplied, resolved_admin):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        key, info = vault.enroll_generated_key(
            req.tenant_id, current_epoch, req.target_url,
            req.db_connection_string, req.scopes)
        return {"api_key": key, "tenant_id": req.tenant_id,
                "epoch": current_epoch, "radius": info["radius"],
                "transparency_root": vault.transparency_root(),
                "note": "Store this key now; it is shown once."}

    @sapp.post("/secure/mint-token")
    async def mint_token(req: _MintRequest, request: Request):
        supplied = request.headers.get("x-vrl1-admin-key", "")
        if not _hmac.compare_digest(supplied, resolved_admin):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        exp = int(time.time()) + req.exp_seconds
        try:
            token = vault.mint_agent_token(
                req.tenant_id, scopes=req.scopes, exp=exp,
                path_prefix=req.path_prefix, max_uses=req.max_uses)
        except ValueError as e:
            return JSONResponse(status_code=400, content={"detail": str(e)})
        return {"capability_token": token, "tenant_id": req.tenant_id,
                "scopes": req.scopes, "exp": exp,
                "path_prefix": req.path_prefix, "max_uses": req.max_uses,
                "note": "Store this token now; it is shown once."}

    async def _forward(target: dict, path: str, request: Request, body: bytes):
        url = f"{target['target_url']}/{path}" if path else target["target_url"]
        try:
            async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
                upstream = await client.request(request.method, url, content=body or None)
        except httpx.HTTPError:
            return JSONResponse(status_code=502, content={"detail": "Bad gateway"})
        try:
            payload = upstream.json()
        except ValueError:
            payload = {"upstream_text": upstream.text}
        return JSONResponse(status_code=upstream.status_code, content={
            "tenant_id": target["tenant_id"], "upstream_status": upstream.status_code,
            "upstream_response": payload})

    @sapp.api_route("/mcp/dispatch/{path:path}", methods=sorted(_FORWARD_METHODS))
    async def sdispatch(path: str, request: Request):
        h = request.headers
        body = await request.body()
        # Capability-token path (also accepts Authorization: Bearer <token>).
        cap_token = h.get("x-vrl1-capability", "")
        authz = h.get("authorization", "")
        if authz.lower().startswith("bearer "):
            cap_token = cap_token or authz[7:].strip()
        if cap_token:
            try:
                target = vault.authenticate_agent_token(
                    cap_token, method=request.method, path=request.url.path)
            except (PermissionError, ValueError):
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
            return await _forward(target, path, request, body)
        # Full key + proof-of-possession path.
        api_key = h.get("x-api-key")
        tenant = h.get("x-vrl1-tenant")
        nonce = h.get("x-vrl1-nonce")
        proof = h.get("x-vrl1-proof")
        try:
            epoch = int(h.get("x-vrl1-epoch", ""))
            ts = int(h.get("x-vrl1-timestamp", ""))
        except ValueError:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        if not (api_key and tenant and nonce and proof):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        try:
            target = vault.authenticate(
                tenant_id=tenant, api_key=api_key, epoch=epoch,
                current_epoch=current_epoch, nonce=nonce, ts=ts,
                method=request.method, path=request.url.path, body=body, proof=proof)
        except (PermissionError, KeyError, ValueError):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await _forward(target, path, request, body)

    return sapp


_SECURE_UI_HTML = """<!doctype html><title>VRL-1 Secure Gateway</title>
<h1>HyperNexus VRL-1 — Secure Mode</h1>
<p>Enroll a tenant key (shown once), mint a capability token for an agent, then
dispatch with proof-of-possession headers or a capability token.</p>
<hr>
<h2>Enroll key</h2>
<label>Tenant <select id="t"><option>tenant_a</option><option>tenant_b</option></select></label>
<label>Target URL <input id="u" value="https://a.example.com" size="40"></label>
<label>Admin key <input id="k" type="password" size="24"></label>
<button onclick="enroll()">Enroll key</button>
<hr>
<h2>Mint agent token (capability-attenuated)</h2>
<label>Tenant <select id="mt"><option>tenant_a</option><option>tenant_b</option></select></label>
<label>Scopes (comma-sep) <input id="ms" value="read:leads" size="20"></label>
<label>Path prefix <input id="mp" value="/mcp/dispatch/leads" size="24"></label>
<label>Max uses <input id="mm" type="number" value="5" size="6"></label>
<button onclick="mint()">Mint token</button>
<hr>
<h2>Dispatch with capability token</h2>
<label>Token <input id="ct" size="60"></label>
<label>Path <input id="cp" value="/mcp/dispatch/leads" size="24"></label>
<button onclick="dispatchCap()">Dispatch</button>
<pre id="out"></pre>
<script>
fetch('/secure/demo-admin-key').then(r=>r.ok?r.json():null).then(d=>{if(d&&d.admin_key)document.getElementById('k').value=d.admin_key}).catch(()=>{});
async function enroll(){
  const r = await fetch('/secure/enroll',{method:'POST',headers:{'content-type':'application/json','x-vrl1-admin-key':document.getElementById('k').value},
    body:JSON.stringify({tenant_id:document.getElementById('t').value,
      target_url:document.getElementById('u').value, db_connection_string:'sqlite:///demo.db', scopes:['*']})});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}
async function mint(){
  const r = await fetch('/secure/mint-token',{method:'POST',headers:{'content-type':'application/json','x-vrl1-admin-key':document.getElementById('k').value},
    body:JSON.stringify({tenant_id:document.getElementById('mt').value,
      scopes:document.getElementById('ms').value.split(',').map(s=>s.trim()).filter(Boolean),
      path_prefix:document.getElementById('mp').value,
      max_uses:parseInt(document.getElementById('mm').value||'0',10)})});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}
async function dispatchCap(){
  const tok = document.getElementById('ct').value;
  const p = document.getElementById('cp').value;
  const r = await fetch(p,{method:'POST',headers:{'content-type':'application/json','x-vrl1-capability':tok},
    body:JSON.stringify({x:1})});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}
</script>"""
