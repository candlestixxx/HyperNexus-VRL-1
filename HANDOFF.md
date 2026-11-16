# Session Handoff — HyperNexus VRL-1

## Current state (2026-11-16)
- Version: see `VERSION.md` (single source; read via `vrl1_version.app_version()`). Latest: v1.3.0.
- Branch: `main` only; no submodules; pushed to `origin` (github.com/candlestixxx/HyperNexus-VRL-1).
- Tests: 40 passing (`python -m pytest -q`). Note: TestClient-based tests need socket access — inside the Muse sandbox they fail with WinError on socketpair; run escalated or locally.

## What shipped this session
- v1.1.0 (`c8a8297`): float radial math core, vault, standalone gateway, manifesto/spec docs.
- v1.2.0 (`95be886`): Tier-1 integer-torus engine (`core/vrl1_algo.py`), `SecureRadialVault`, AEAD records, proof-of-possession, nonce ledger, `docs/SPEC.md`. Corrected flaws in a pasted prototype: nonce removed from coordinate derivation, radius never projected into rings, stolen vectors useless without the key.
- v1.3.0: secure gateway integration (`create_secure_app`, `/secure/enroll`, `/secure/ui`, `X-VRL1-*` headers), Merkle transparency log, invariant fuzz test, benchmark harness + measured doc, CI workflow, TODO P1–P8 all closed.

## Architecture in one paragraph
`src/` = production portal gateway (FastAPI, Fernet vault, router, DB pools, MCP JSON-RPC). `core/` = math engines: legacy float (`vector_math.py`, `vault.py`) plus Tier-1 (`vrl1_algo.py`, `secure_vault.py`, `transparency.py`). `api/gateway.py` = standalone demo app + secure-mode app. Entry points: `python main.py` (8000), `uvicorn api.gateway:app` (8001, demo).

## Known flags (do not "fix" silently)
- Default master keys are hardcoded in `src/config.py` and `docker-compose.yml` for local demo. They are in git history from v1.0.0; purge only on explicit owner order. Secure mode (`create_secure_app`) already refuses demo keys unless `demo=True`.
- Benchmark numbers in `docs/BENCHMARKS.md` are micro-benchmarks only. No external performance/energy claim until the full HTTP crucible exists.
- ChaCha20Poly1305 substitutes for XChaCha20 (installed `cryptography` lacks XChaCha) — recorded in CHANGELOG v1.2.0.

## What remains and why it's ordered this way
ROADMAP Milestones 4–5: VSS threshold release, KMS/HSM custody, capability tokens, CUSUM, shared stores, then Rust port, ZK (field-native commitment designed with the circuit), BFT, TLA+. Each is multi-week; they are milestones, not TODO items.

## Resume commands
```powershell
pip install -r requirements.txt
python -m pytest -q
python benchmarks\bench_gateway.py
python main.py
```
Git in this sandbox needs: `$env:GIT_CONFIG_COUNT='1'; $env:GIT_CONFIG_KEY_0='safe.directory'; $env:GIT_CONFIG_VALUE_0='C:/Users/jakeg/workspace/HyperNexus VRL-1'` and escalated (real-user) execution for push, since sandbox credentials return 401.
