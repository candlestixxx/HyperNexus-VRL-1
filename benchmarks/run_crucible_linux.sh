#!/usr/bin/env bash
# Phase-1 crucible on Linux/WSL: VRL-1 secure gateway vs Kong/Nginx baselines.
#
# Prereqs: docker (for Kong), nginx, python 3.10+, httpx.
#   pip install -r requirements.txt
set -euo pipefail

UPSTREAM="http://127.0.0.1:9000"

# 1. Mock upstream (a trivial echo server).
echo "[crucible] starting mock upstream on 9000"
python -m http.server 9000 --bind 127.0.0.1 &>/dev/null &
UP_PID=$!
trap 'kill $UP_PID 2>/dev/null || true' EXIT

# 2. VRL-1 secure gateway.
echo "[crucible] starting VRL-1 gateway on 8443"
export VRL1_MASTER_KEY="bench-master-key-32-bytes-minimum!!"
export VRL1_ADMIN_KEY="bench-admin"
python serve.py &>/dev/null &
VRL_PID=$!
trap 'kill $VRL_PID 2>/dev/null || true' EXIT
sleep 3

# 3. Kong baseline (docker).
echo "[crucible] starting Kong on 8000 (docker)"
docker run -d --name vrl1-kong -p 8000:8000 \
  -e KONG_DECLARATIVE_CONFIG=/etc/kong/kong.yml \
  -v "$PWD/deploy/kong/kong.yml:/etc/kong/kong.yml:ro" \
  -e KONG_DATABASE=off kong:latest >/dev/null
trap 'docker rm -f vrl1-kong 2>/dev/null || true' EXIT

# 4. Run the load generator against each (this is where you plug your wrk/k6
#    or reuse benchmarks/bench_crucible.py against a live socket).
echo "[crucible] ready. Drive with: wrk -t8 -c64 -d30s --latency http://127.0.0.1:8000/dispatch"
echo "[crucible] VRL-1 at https://127.0.0.1:8443 (TLS), Kong at http://127.0.0.1:8000"
wait
