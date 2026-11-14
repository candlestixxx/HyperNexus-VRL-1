# HyperNexus VRL-1: Universal Multi-Tenant API Gateway

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](VERSION.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-18%20passed-brightgreen.svg)](tests/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

**HyperNexus VRL-1 (Virtual Routing Layer 1)** is an intelligent, zero-trust, multi-tenant API gateway and dynamic control plane engineered for **United Beats LLC** and enterprise integration ecosystems.

It routes, manages, and isolates database connections and third-party API payloads across diverse companies with zero cross-tenant data leakage, powered by an **$O(1)$ Radial Vector Secret Vault** and native **Model Context Protocol (MCP)** agent integration.

---

## Key Features

- **Radial Vector Secret Vault**: Tenants orbit in concentric polar coordinate rings $(r, \theta, z)$. Database URIs, OAuth tokens, and API keys are protected by envelope cipher encryption, guaranteeing $O(1)$ spatial lookup and absolute boundary isolation.
- **AI-Driven Dynamic Switchboard**: Automatically resolves inbound tenant identities via `X-API-Key`, Bearer tokens, host domain headers, or payload inspection, forwarding traffic to isolated corporate silos with sub-millisecond overhead.
- **Zero-Downtime Hot Onboarding**: Register new businesses at runtime via database write (`POST /api/v1/tenants`). The in-memory matrix refreshes instantly without server restarts.
- **Multi-Tenant Database Isolation**: Dedicated database connection pooling ensures transactions land exclusively in that company's database schema (PostgreSQL, MongoDB, SQLite, MySQL) with an immutable audit ledger.
- **TormentNexus MCP AI Agent Hooks**: Native JSON-RPC 2.0 Model Context Protocol server endpoints allow autonomous AI agents (Hermes, Ollama, Claude, Gemini) to query routing state without privilege escalation.
- **Interactive Developer Portal**: Sleek dark-mode SPA featuring an HTML5 Canvas Radial Vector visualizer, live switchboard simulator, tenant management forms, and real-time telemetry.

---

## Architecture Topology

```
                  INBOUND API TRAFFIC & AGENT REQUESTS
            (Headers: X-API-Key | Bearer | Host Domain | Payload)
                                   │
                                   ▼
          ┌──────────────────────────────────────────────────┐
          │         HyperNexus VRL-1 Gateway Core            │
          │    FastAPI Non-Blocking Async Proxy Pipeline     │
          └────────────────────────┬─────────────────────────┘
                                   │
               ┌───────────────────┴───────────────────┐
               ▼                                       ▼
  ┌────────────────────────┐              ┌────────────────────────┐
  │   Radial Vector Vault  │              │ Token-Bucket Rate      │
  │ Concentric Ring Spaces │              │ Traffic Shaper         │
  │     (r, θ, z)          │              └────────────────────────┘
  └────────────┬───────────┘                           │
               │ Verified Tenant Context               │
               ▼                                       ▼
  ┌────────────────────────────────────────────────────────────────┐
  │            Dynamic AI Switchboard & Schema Router              │
  └────────┬───────────────────────┬───────────────────────┬───────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│    United Beats     │ │ Excel Legacy Realty │ │ HyperNexus Core     │
│    (Ring 1: Ent)    │ │   (Ring 2: Pro)     │ │   (Ring 0: Core)    │
│  Postgres DB Pool   │ │   Mongo DB Pool     │ │   SQLite DB Pool    │
│ Upstream Stream API │ │ Upstream Lead Webhk │ │ Orchestration Silo  │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘
           │                       │                       │
           └───────────────────────┼───────────────────────┘
                                   ▼
                    Model Context Protocol (MCP)
                     Hermes & Ollama AI Swarms
```

---

## Quickstart

### Run with Python
```bash
# Clone repository
git clone https://github.com/candlestixxx/HyperNexus-VRL-1.git
cd HyperNexus-VRL-1

# Launch using startup script
start.bat      # Windows
./start.sh     # Linux / macOS / WSL
```

### Run with Docker Compose
```bash
docker compose up -d --build
```

### Access Points
- **Developer Portal UI**: [http://localhost:8000/portal](http://localhost:8000/portal)
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## Testing & Quality Assurance

Run the automated test suite:
```bash
python -m pytest -v
```
All 18 tests cover cryptographic envelope roundtrips, radial coordinate derivation, dynamic routing, database audit pooling, and MCP JSON-RPC compliance.

---

## Project Governance & Documentation

- [BUSINESS_PLAN.md](file:///C:/Users/jakeg/workspace/HyperNexus%20VRL-1/BUSINESS_PLAN.md): Full commercialization strategy, financial projections, and GTM plan.
- [VISION.md](file:///C:/Users/jakeg/workspace/HyperNexus%20VRL-1/VISION.md): Ultimate foundational philosophy and user satisfaction design.
- [MEMORY.md](file:///C:/Users/jakeg/workspace/HyperNexus%20VRL-1/MEMORY.md): Architectural memory, traits, and algorithmic choices.
- [DEPLOY.md](file:///C:/Users/jakeg/workspace/HyperNexus%20VRL-1/DEPLOY.md): Comprehensive deployment and environment setup instructions.
- [IDEAS.md](file:///C:/Users/jakeg/workspace/HyperNexus%20VRL-1/IDEAS.md): Aggressive ideas for language ports (Rust/PyO3) and eBPF acceleration.
- [ROADMAP.md](file:///C:/Users/jakeg/workspace/HyperNexus%20VRL-1/ROADMAP.md): Major long-term structural milestones.
- [TODO.md](file:///C:/Users/jakeg/workspace/HyperNexus%20VRL-1/TODO.md): Granular short-term tasks.
- [CHANGELOG.md](file:///C:/Users/jakeg/workspace/HyperNexus%20VRL-1/CHANGELOG.md): Detailed release notes for v1.0.0.
- [HANDOFF.md](file:///C:/Users/jakeg/workspace/HyperNexus%20VRL-1/HANDOFF.md): Model session continuity notes.

---

## License
MIT License. &copy; 2026 United Beats LLC & HyperNexus Ecosystem.
