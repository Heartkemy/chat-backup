#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

DATE=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$DATE] Starting chat backup..."

# Build the chat viewer (WhatsApp only, Signal needs keychain)
python3 chat_backup/builder.py 2>&1

# Keep the HTTP server running (start if not already running)
if lsof -ti:8080 >/dev/null 2>&1; then
  echo "[$DATE] Server already running on :8080"
else
  cd "$DIR/data"
  nohup python3 -m http.server 8080 > /dev/null 2>&1 &
  echo "[$DATE] Started server on :8080"
fi

echo "[$DATE] Done"
