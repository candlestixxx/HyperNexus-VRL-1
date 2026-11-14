@echo off
setlocal enabledelayedexpansion

echo ==================================================================
echo   HyperNexus VRL-1: Universal Multi-Tenant API Gateway
echo   United Beats Flagship Control Plane & Radial Vector Vault
echo ==================================================================

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.10+ is required but not found in PATH.
    pause
    exit /b 1
)

REM Check or create virtual environment if desired
if not exist "venv" (
    echo [INFO] Creating local virtual environment 'venv'...
    python -m venv venv
)

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Install dependencies
echo [INFO] Verifying requirements...
pip install -r requirements.txt --quiet

REM Launch Gateway
echo [INFO] Launching HyperNexus VRL-1 Gateway on http://localhost:8000
echo [INFO] Access Developer Portal at http://localhost:8000/portal
echo [INFO] Interactive OpenAPI Documentation at http://localhost:8000/docs
python main.py

pause
