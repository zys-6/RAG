#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-10.42.0.125}"

curl -fsS "http://${HOST}:12355/openapi.json" >/dev/null
curl -fsS "http://${HOST}:12356/openapi.json" >/dev/null
curl -fsS "http://${HOST}:12357/openapi.json" >/dev/null

echo "Stage 1 remote OpenAPI smoke checks passed for ${HOST}"
