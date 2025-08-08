#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")"/..; pwd)"

# Backend dir auto-detect
if [ -d "$ROOT/backend" ]; then
  BE_DIR="$ROOT/backend"
else
  BE_DIR="$ROOT"
fi

# Pick requirements.txt
if [ -f "$BE_DIR/requirements.txt" ]; then
  REQ_FILE="$BE_DIR/requirements.txt"
elif [ -f "$ROOT/requirements.txt" ]; then
  REQ_FILE="$ROOT/requirements.txt"
else
  REQ_FILE="$BE_DIR/requirements.txt"
  cat > "$REQ_FILE" <<'EOF'
fastapi==0.111.0
uvicorn[standard]==0.30.1
pydantic==2.8.2
python-multipart==0.0.9
pytesseract==0.3.10
pdf2image==1.17.0
Pillow==10.3.0
regex==2024.5.15
rapidfuzz==3.10.0
EOF
fi

# Backend up
cd "$BE_DIR"
python3 -m venv .venv || true
source .venv/bin/activate
pip3 install -r "$REQ_FILE"
(lsof -ti:8000 | xargs kill -9) >/dev/null 2>&1 || true
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > "$ROOT/backend_dev.log" 2>&1 &

# Frontend up
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then npm i; fi
export NEXT_PUBLIC_API_BASE="${NEXT_PUBLIC_API_BASE:-http://localhost:8000}"
(lsof -ti:3000 | xargs kill -9) >/dev/null 2>&1 || true
nohup npm run dev > "$ROOT/frontend_dev.log" 2>&1 &

# Open browser on macOS
if command -v open >/dev/null 2>&1; then
  open "http://localhost:3000"
fi

echo "Backend log: $ROOT/backend_dev.log"
echo "Frontend log: $ROOT/frontend_dev.log"
