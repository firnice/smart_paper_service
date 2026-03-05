#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deprecated: use ./start_service.sh dev"

if [ "$#" -eq 0 ]; then
  exec "$ROOT_DIR/start_service.sh" dev
else
  exec "$ROOT_DIR/start_service.sh" "$@"
fi
