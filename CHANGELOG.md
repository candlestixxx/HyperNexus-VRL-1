# Changelog — HyperNexus VRL-1

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-16

### Added
- **VRL-1 Math Core (`core/`)**: `RadialVectorEngine` implementing Proofs I–III (SHA-256 spatilization to `(r, θ)`, disjoint-ring radial gate, O(1)-in-N angular routing) with numpy; `RadialVault` in-memory vault indexed by angular shard with overlap-rejecting tenant registration.
- **Standalone Async Gateway (`api/gateway.py`)**: `POST /mcp/dispatch/{path:path}` resolving `X-API-Key` at the math layer, forwarding via `httpx.AsyncClient`, instant 403 with no DB/log write on rejection.
- **Geometric Proof Tests**: `tests/test_zero_trust.py` + `tests/test_gateway_dispatch.py` (10 new tests; 28 total passing), including cross-tenant vector rejection and upstream-never-called assertions.
- **Docs**: `docs/MATHEMATICS.md` (proofs + honest limits), `MANIFESTO.md` (investor/partner narrative), `LLM_BUILD_INSTRUCTIONS.md` (agent build directive).
- `numpy` added to `requirements.txt`.

## [1.0.0] - 2026-11-14

### Added
- **Core Architecture**:
  - High-throughput asynchronous FastAPI control plane in `src/main.py`.
  - Configurable settings engine with Pydantic v2 `SettingsConfigDict` in `src/config.py`.
- **Radial Vector Secret Vault (`src/vault/`)**:
  - Mathematical tree-ring radial vector coordinate derivation $(r, \theta, z)$.
  - Zero cross-tenant data leakage guarantees with envelope encryption via Fernet & PBKDF2HMAC.
  - Runtime hot-registration and atomic persistence to `data/radial_vault.json`.
- **Dynamic AI Switchboard Router (`src/router/`)**:
  - Multi-vector tenant resolution across `X-API-Key`, Bearer tokens, Host domains, `X-Tenant-ID`, and query/body fallbacks.
  - Per-tenant token-bucket rate limiter enforcing traffic quotas and preventing noisy-neighbor degradation.
  - Upstream HTTP proxy forwarding with simulated loopback fallback for offline testing.
- **Multi-Tenant Database Pool Manager (`src/db/`)**:
  - Dynamic connection pooling per tenant schema.
  - Tenant-isolated SQLite transaction audit logging (`data/audit_{company_id}.sqlite3`).
- **Model Context Protocol (MCP) Server (`src/mcp/`)**:
  - JSON-RPC 2.0 compliant MCP server endpoints (`/mcp/rpc`, `/mcp/tools`, `/mcp/context`).
  - Isolated AI agent context buffers for Hermes Agent and Ollama swarms.
- **Developer Portal UI (`src/portal/index.html`)**:
  - Modern, responsive dark-mode Single Page Application.
  - Interactive HTML5 Canvas Radial Vector visualizer rendering concentric security rings.
  - Dynamic API Switchboard simulator with real-time latency and payload inspection.
  - Zero-downtime tenant onboarding form.
  - Live database audit ledger viewer and MCP capability monitor.
- **Testing & Tooling**:
  - 18 comprehensive pytest test cases covering vault security, routing, MCP hooks, and end-to-end API flows.
  - Automated deployment scripts: `start.bat`, `start.sh`, `Dockerfile`, `docker-compose.yml`.
  - Comprehensive documentation suite: `BUSINESS_PLAN.md`, `VISION.md`, `MEMORY.md`, `DEPLOY.md`, `IDEAS.md`, `ROADMAP.md`, `TODO.md`, `HANDOFF.md`, `README.md`.
