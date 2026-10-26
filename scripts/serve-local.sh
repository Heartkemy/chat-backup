#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${CHAT_BACKUP_DIR:-$ROOT/data}"
PORT="${CHAT_BACKUP_PORT:-8765}"

exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DATA_DIR"
