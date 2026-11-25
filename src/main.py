"""
HyperNexus VRL-1: Universal Multi-Tenant API Gateway & Control Plane
United Beats Flagship Integration Hub.

Features:
- O(1) Radial Vector Secret Vault with envelope encryption.
- Dynamic AI-driven switchboard with zero cross-tenant leakage.
- Isolated multi-tenant database connection pooling & transaction auditing.
- Model Context Protocol (MCP) server & AI context hooks.
- Real-time developer portal UI and live switchboard simulator.
"""

import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, Header, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.models import (
    TenantRegistrationRequest,
    TenantContext,
    DispatchResponse
)
from src.vault.radial_vault import RadialVectorVault
from src.router.dynamic_router import DynamicTenantRouter
from src.db.pool_manager import db_pool_manager
from src.mcp.hooks import mcp_bridge
from src.telemetry import telemetry_tracker

# Loudly flag the shipped demo key: the legacy `src/` portal is for local
# exploration only. Production must use `serve.py` (secure mode) with a real
# KMS/env master key.
if settings.VAULT_MASTER_KEY == "hyp-vrl1-radial-master-key-32bytes-secret!":
    import warnings as _warnings
    _warnings.warn(
        "HyperNexus `src/` portal is running with the SHIPPED DEMO MASTER KEY. "
        "This is NOT secure; use `python serve.py` (secure mode) for anything real.",
        stacklevel=2)

# Instantiate FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Universal Multi-Tenant API Gateway and Dynamic Control Plane with Radial Vector Secret Vault and Model Context Protocol (MCP) Integration.",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Gateway Core Singletons
vault = RadialVectorVault()
router = DynamicTenantRouter(vault=vault)

# Dependency for tenant resolution
async def get_current_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    x_tenant_id: Optional[str] = Header(None)
) -> TenantContext:
    """Dependency that resolves tenant from headers, tokens, host domain, or query params."""
    return await router.resolve_tenant(request, x_api_key, x_tenant_id)


# ---------------------------------------------------------------------------
# UI DEVELOPER PORTAL ROUTES
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
@app.get("/portal", response_class=HTMLResponse)
async def serve_developer_portal():
    """Serves the interactive United Beats / HyperNexus VRL-1 Developer Portal."""
    portal_path = os.path.join(os.path.dirname(__file__), "portal", "index.html")
    if os.path.exists(portal_path):
        with open(portal_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>HyperNexus VRL-1 Developer Portal initializing...</h2>")


# ---------------------------------------------------------------------------
# CORE DYNAMIC SWITCHBOARD & DISPATCH ENDPOINT
# ---------------------------------------------------------------------------

@app.api_route(
    "/mcp/dispatch/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    summary="Dynamic Multi-Tenant API Switchboard Dispatcher"
)
async def dynamic_dispatch_route(
    path: str,
    request: Request,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """
    Universal Switchboard:
    1. Intercepts incoming payload.
    2. Resolves tenant via Radial Vector Vault (zero cross-tenant contamination).
    3. Enforces tenant token bucket rate-limit.
    4. Connects to isolated tenant database pool and logs audit trail.
    5. Forwards request to tenant's target API endpoint.
    6. Synchronizes state to MCP AI Agent context buffer.
    """
    result = await router.dispatch_request(path, request, tenant)
    return JSONResponse(status_code=200, content=result)


# ---------------------------------------------------------------------------
# TENANT MANAGEMENT & ONBOARDING (ZERO-DOWNTIME REGISTRATION)
# ---------------------------------------------------------------------------

@app.get("/api/v1/tenants", summary="List Registered Tenants")
async def list_tenants():
    """Lists registered tenants with masked secrets and radial polar coordinates."""
    return vault.list_all_tenants(mask_secrets=True)

@app.post("/api/v1/tenants", summary="Onboard New Tenant at Runtime")
async def register_tenant(req: TenantRegistrationRequest):
    """
    Hot-registers a new business into the Radial Vector Vault without server restart.
    Instantly provisions isolated database connection pool and routing coordinates.
    """
    created = vault.register_tenant(req)
    return {
        "status": "registered",
        "company_id": created.company_id,
        "radial_coords": created.radial_coords.model_dump(),
        "message": f"Tenant '{created.company_name}' registered successfully into Radial Ring {created.radial_coords.r}."
    }

@app.get("/api/v1/tenants/{company_id}", summary="Get Tenant Details")
async def get_tenant_details(company_id: str):
    """Fetches public topology details for a single company."""
    tenant = vault.get_tenant_by_company_id(company_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    dump = tenant.model_dump()
    dump["db_connection"] = "••••••••[Radial-Encrypted]••••••••"
    return dump


# ---------------------------------------------------------------------------
# ISOLATED DATABASE AUDIT LEDGER ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/api/v1/audit/{company_id}", summary="Get Isolated Tenant Transaction Audit Ledger")
async def get_audit_ledger(company_id: str, limit: int = 25):
    """Retrieves transaction history executed exclusively in the tenant's isolated database."""
    tenant = vault.get_tenant_by_company_id(company_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found.")
    
    session = db_pool_manager.get_session(
        company_id=tenant.company_id,
        db_connection_uri=tenant.db_connection,
        db_type=tenant.db_type
    )
    return session.get_recent_transactions(limit=limit)


# ---------------------------------------------------------------------------
# MODEL CONTEXT PROTOCOL (MCP) SERVER & AI AGENT INTEGRATION
# ---------------------------------------------------------------------------

@app.get("/mcp/tools", summary="MCP Tool Definitions")
async def get_mcp_tools():
    """Returns MCP tools available for autonomous AI agents."""
    return {
        "tools": mcp_bridge.get_supported_mcp_tools()
    }

@app.get("/mcp/context/{company_id}", summary="Get Isolated MCP Context Window")
async def get_mcp_context(company_id: str):
    """Returns the isolated context memory stream for an AI agent bound to a specific tenant."""
    return {
        "company_id": company_id,
        "context_stream": mcp_bridge.get_tenant_mcp_history(company_id)
    }

@app.post("/mcp/rpc", summary="MCP JSON-RPC 2.0 Handler")
async def handle_mcp_rpc(request: Request):
    """Standard JSON-RPC 2.0 interface for Model Context Protocol clients."""
    try:
        body = await request.json()
        method = body.get("method")
        msg_id = body.get("id", 1)
        
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": mcp_bridge.get_supported_mcp_tools()}
            }
        elif method == "tools/call":
            params = body.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            
            if name == "vrl1_get_radial_status":
                tenants_list = vault.list_all_tenants(mask_secrets=True)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": str(tenants_list)}]}
                }
            elif name == "vrl1_query_tenant_ledger":
                company_id = arguments.get("company_id")
                limit = arguments.get("limit", 10)
                tenant = vault.get_tenant_by_company_id(company_id)
                if not tenant:
                    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": "Tenant not found"}}
                session = db_pool_manager.get_session(tenant.company_id, tenant.db_connection, tenant.db_type)
                logs = session.get_recent_transactions(limit=limit)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": str(logs)}]}
                }
            else:
                return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method {name} not found"}}
        else:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Unsupported method {method}"}}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}


# ---------------------------------------------------------------------------
# TELEMETRY & HEALTH MONITORING
# ---------------------------------------------------------------------------

@app.get("/api/v1/telemetry", summary="System Telemetry & Performance")
async def get_telemetry():
    """Returns live request counts, error rates, and average latencies."""
    return telemetry_tracker.get_summary()

@app.get("/health", summary="Gateway Health Check")
async def health_check():
    """System health check and uptime probe."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "radial_vault_active": True,
        "tenants_loaded": len(vault.list_all_tenants()),
        "mcp_enabled": settings.MCP_ENABLED
    }


if __name__ == "__main__":
    import uvicorn
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} on http://{settings.HOST}:{settings.PORT}")
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=True)
