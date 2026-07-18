#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${E2E_API_PORT:-8000}"

exec "$ROOT/.venv/bin/uvicorn" tech_support_api.main:app \
  --host 127.0.0.1 \
  --port "$PORT" \
  --log-level warning
