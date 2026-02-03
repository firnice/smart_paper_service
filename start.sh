#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/server.log}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN=python
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found. Please install Python 3 and try again."
  exit 1
fi

if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti tcp:"$PORT" || true)"
  if [ -n "$PIDS" ]; then
    echo "Port $PORT is in use. Killing: $PIDS"
    kill -9 $PIDS
    sleep 0.3
  fi
else
  echo "lsof not found. Please ensure port $PORT is free."
fi

cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

pip install -r requirements.txt

if [ ! -f "app/core/llm_secrets.py" ]; then
  echo "Missing app/core/llm_secrets.py"
  echo "Run: cp app/core/llm_secrets.example.py app/core/llm_secrets.py"
  exit 1
fi

mkdir -p "$LOG_DIR"
echo "Logging to $LOG_FILE"
uvicorn app.main:app --reload --port "$PORT" --log-level info 2>&1 | tee -a "$LOG_FILE"
