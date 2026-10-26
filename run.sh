#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

python3 chat_backup/builder.py
printf 'Built local archive. View it only with ./scripts/serve-local.sh\n'
