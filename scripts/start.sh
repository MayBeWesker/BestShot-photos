#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_root="$project_root/backend"
frontend_root="$project_root/frontend"

if [[ ! -x "$backend_root/.venv/bin/python" ]]; then
  python3 -m venv "$backend_root/.venv"
  "$backend_root/.venv/bin/python" -m pip install -r "$backend_root/requirements.txt"
fi

if ! "$backend_root/.venv/bin/python" -c "import pillow_heif, httpx" >/dev/null 2>&1; then
  echo "Updating backend dependencies (image formats and DeepSeek)..."
  "$backend_root/.venv/bin/python" -m pip install -r "$backend_root/requirements.txt"
fi

if [[ ! -d "$frontend_root/node_modules" ]]; then
  (cd "$frontend_root" && npm install)
fi

cleanup() { kill "$backend_pid" "$frontend_pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
(cd "$backend_root" && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000) & backend_pid=$!
(cd "$frontend_root" && npm run dev) & frontend_pid=$!
echo "BestShot-photos: http://127.0.0.1:5173"
wait

