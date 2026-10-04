#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'Install Python dependencies first: uv venv --python 3.12 && uv pip install -r requirements.txt -r app/requirements-web.txt'
  exit 1
fi
if [[ ! -d frontend/node_modules ]]; then
  npm --prefix frontend ci
fi
.venv/bin/python -m uvicorn app.api:app --host 127.0.0.1 --port 8502 &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT INT TERM
npm --prefix frontend run dev
