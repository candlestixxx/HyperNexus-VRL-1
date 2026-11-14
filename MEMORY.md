# Architectural Memory & Codebase Traits — HyperNexus VRL-1

## 1. Architectural Observations
- **FastAPI Async Core**: Built on Python 3.10+ async/await primitives with `httpx.AsyncClient` connection pools. This guarantees maximum non-blocking I/O throughput during proxy dispatch.
- **Radial Vector Mathematics**:
  - The polar coordinate tuple $(r, \theta, z)$ maps tenant isolation:
    - Radius $r$ directly indexes security rings ($0.5$ for Core, $1.0$ for United Beats, $1.5$ for Pro Realty, $2.0$ for Standard).
    - Angle $\theta \in [0, 2\pi)$ distributes tenants uniformly across the ring via SHA-256 modulo projection.
    - Depth $z$ represents the rotation depth for PBKDF2/Fernet envelope cipher keys.
- **Zero Cross-Tenant Leakage Guarantee**:
  - Each company has its own isolated audit database (`data/audit_{company_id}.sqlite3`) and dedicated database session pool in `MultiTenantDBPoolManager`.
  - Context windows in `MCPAgentBridge` are mapped strictly by `company_id`.
- **Dynamic Onboarding**:
  - Registering a tenant via `POST /api/v1/tenants` updates `_registry_by_hash`, `_company_to_hash`, and `_domain_to_hash` atomically under an `RLock`, followed by atomic disk persistence (`data/radial_vault.json`).

## 2. Codebase Traits & Conventions
- **Strict Typing**: Full Pydantic v2 schemas across requests, models, and telemetry.
- **Deprecation Cleanliness**: Avoided `datetime.utcnow()` in favor of `datetime.now(timezone.utc)`; avoided `class Config` in favor of `model_config = SettingsConfigDict(...)`.
- **Graceful Loopback Simulation**: When target upstream APIs are mock URLs or offline during tests/local development, `DynamicTenantRouter` captures the `httpx.ConnectError` and simulates upstream delivery without crashing the pipeline, returning structured simulation data.

## 3. Key File Layout
- `main.py`: Root launcher script.
- `src/main.py`: FastAPI application wiring all endpoints and static routes.
- `src/vault/radial_vault.py`: Concentric ring vector vault and secret encryption.
- `src/router/dynamic_router.py`: Token bucket rate limiting and proxy dispatcher.
- `src/db/pool_manager.py`: Multi-tenant DB session manager and audit logger.
- `src/mcp/hooks.py`: MCP tool definitions and AI agent context bridge.
- `src/portal/index.html`: Responsive developer portal UI with HTML5 canvas visualizer.
- `tests/`: 18 comprehensive unit and end-to-end integration tests.
