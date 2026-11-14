"""
HyperNexus VRL-1: Root Launcher
United Beats Universal Multi-Tenant API Gateway.
"""

import sys
import os

# Ensure project root is in PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import app, vault, router
import uvicorn
from src.config import settings

if __name__ == "__main__":
    print(f"==================================================================")
    print(f"  HyperNexus VRL-1: Universal Multi-Tenant API Gateway")
    print(f"  United Beats Flagship Control Plane & Radial Vector Vault")
    print(f"  Running on: http://{settings.HOST}:{settings.PORT}")
    print(f"  Developer Portal: http://localhost:{settings.PORT}/portal")
    print(f"  Interactive OpenAPI: http://localhost:{settings.PORT}/docs")
    print(f"==================================================================")
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=True)
