#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

DATE=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$DATE] Starting chat backup..."

# Use Apple's system python: stable binary path, so macOS permissions persist.
# Homebrew python is a symlink into Cellar and changes on every upgrade,
# which resets TCC grants and causes repeated authorization prompts.
PY=/usr/bin/python3

# Build the chat viewer (WhatsApp only, Signal needs keychain)
"$PY" chat_backup/builder.py 2>&1

# Keep the HTTP server running (start if not already running)
if lsof -ti:8080 >/dev/null 2>&1; then
  echo "[$DATE] Server already running on :8080"
else
  cd "$DIR/data"
  nohup "$PY" -m http.server 8080 > /dev/null 2>&1 &
  echo "[$DATE] Started server on :8080"
fi

echo "[$DATE] Done"
