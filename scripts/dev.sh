#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")"/..; pwd)"

# Backend
cd "$ROOT"
python3 -m venv .venv || true
source .venv/bin/activate
pip3 install -r requirements.txt
# Port 8000 を占有しているプロセスを停止（あれば）
(lsof -ti:8000 | xargs kill -9) >/dev/null 2>&1 || true
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > "$ROOT/backend_dev.log" 2>&1 &

# Frontend
cd "$ROOT"
if [ ! -d node_modules ]; then npm i; fi
export NEXT_PUBLIC_API_BASE="${NEXT_PUBLIC_API_BASE:-http://localhost:8000}"
# Port 3000 を占有しているプロセスを停止（あれば）
(lsof -ti:3000 | xargs kill -9) >/dev/null 2>&1 || true
nohup npx next dev -H 127.0.0.1 -p 3000 > "$ROOT/frontend_dev.log" 2>&1 &

# Open browser
if command -v open >/dev/null 2>&1; then
  open "http://localhost:3000"
fi

echo "Backend log: $ROOT/backend_dev.log"
echo "Frontend log: $ROOT/frontend_dev.log"
