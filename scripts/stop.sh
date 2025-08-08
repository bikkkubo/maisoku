#!/usr/bin/env bash
set -euo pipefail
# stop Next.js (3000) and uvicorn (8000)
(lsof -ti:3000 | xargs kill -9) >/dev/null 2>&1 || true
(lsof -ti:8000 | xargs kill -9) >/dev/null 2>&1 || true
echo "Stopped processes on :3000 and :8000"
