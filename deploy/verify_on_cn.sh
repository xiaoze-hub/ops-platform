#!/usr/bin/env bash
# Run ON the domestic host after code+env are in place.
set -euo pipefail
cd "$(dirname "$0")/.."
test -f .env || { echo "missing .env"; exit 1; }
docker compose up -d db platform
sleep 8
docker compose ps
echo "--- health ---"
curl -fsS "http://127.0.0.1:8081/api/v1/health" || true
echo
echo "--- platform logs ---"
docker compose logs --tail=40 platform
