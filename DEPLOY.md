# Deployment & Environment Guide — HyperNexus VRL-1

## 1. Prerequisites
- Python 3.10+ (tested on Python 3.14 on Windows and Linux)
- Git 2.30+
- Optional: Docker and Docker Compose

## 2. Local Environment Setup

### Windows
```cmd
git clone https://github.com/candlestixxx/HyperNexus-VRL-1.git
cd "HyperNexus-VRL-1"

REM Automated startup script
start.bat
```

### Linux / macOS / WSL
```bash
git clone https://github.com/candlestixxx/HyperNexus-VRL-1.git
cd HyperNexus-VRL-1

# Automated shell script
chmod +x start.sh
./start.sh
```

### Manual Execution
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Access the interfaces:
- **Developer Portal UI**: [http://localhost:8000/portal](http://localhost:8000/portal)
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 3. Docker Deployment

### Run with Docker Compose
```bash
docker compose up -d --build
```

### Build Single Docker Image
```bash
docker build -t hypernexus-vrl1:latest .
docker run -d -p 8000:8000 --name hypernexus-gateway hypernexus-vrl1:latest
```

---

## 4. Environment Variables Configuration (`.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | Gateway listening address |
| `PORT` | `8000` | Gateway listening port |
| `VAULT_MASTER_KEY` | `hyp-vrl1-radial-...` | Master secret key for Fernet envelope encryption |
| `VAULT_PERSISTENCE_PATH`| `data/radial_vault.json`| Atomic JSON state storage path |
| `MCP_ENABLED` | `true` | Enable TormentNexus MCP server endpoints |
| `OLLAMA_ENDPOINT` | `http://localhost:11434`| Optional local LLM endpoint for AI hooks |
| `HERMES_AGENT_ENDPOINT` | `http://localhost:8081` | Optional Hermes Agent swarm endpoint |

### Secure Mode (Tier-1 gateway, `api/gateway.py`)

The secure app refuses to start without real key material:

```bash
export VRL1_MASTER_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
export VRL1_ADMIN_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(24))')"
uvicorn api.gateway:create_secure_app --factory --port 8001
```

| Variable | Required | Description |
| :--- | :--- | :--- |
| `VRL1_MASTER_KEY` | yes (≥32 bytes) | Master key for tenant/proof/record/signature derivation; refused if missing unless `demo=True` |
| `VRL1_ADMIN_KEY` | yes | Gates `/secure/enroll`; refused if missing unless `demo=True` (which auto-generates and prints it) |

Vault persistence is opt-in via `create_secure_app(persistence_path=...)`: state is written atomically and its transparency root is HMAC-signed, so a rolled-back or forged state file is refused on the next load. In demo mode the auto-generated admin key is printed to stderr and exposed at `/secure/demo-admin-key` only.

---

## 5. Verification & Testing
Execute the complete test suite:
```bash
python -m pytest -v
```
All 18 tests should pass in under 3 seconds.
