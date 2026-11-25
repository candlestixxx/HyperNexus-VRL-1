"""HyperNexus VRL-1 secure gateway — production entrypoint.

Runs `create_secure_app` with env-driven configuration and optional TLS.

Env:
  VRL1_HOST (default 0.0.0.0) · VRL1_PORT (default 8443)
  VRL1_VAULT_PATH (persistence; optional)
  VRL1_MASTER_KEY / VRL1_VAULT_ADDR + VRL1_VAULT_TOKEN (KMS custody)
  VRL1_ADMIN_KEY
  VRL1_TLS_CERT / VRL1_TLS_KEY (enable TLS when both set)

Run:  python serve.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.gateway import create_secure_app  # noqa: E402


def main() -> None:
    host = os.environ.get("VRL1_HOST", "0.0.0.0")
    port = int(os.environ.get("VRL1_PORT", "8443"))
    persistence = os.environ.get("VRL1_VAULT_PATH", "") or None

    app = create_secure_app(persistence_path=persistence)

    import uvicorn
    cert = os.environ.get("VRL1_TLS_CERT", "")
    key = os.environ.get("VRL1_TLS_KEY", "")
    if cert and key:
        print(f"[VRL-1] serving https://{host}:{port} (TLS on)")
        uvicorn.run(app, host=host, port=port, ssl_certfile=cert, ssl_keyfile=key)
    else:
        print(f"[VRL-1] serving http://{host}:{port} (TLS off — set VRL1_TLS_CERT/KEY)")
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
