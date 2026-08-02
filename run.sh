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

echo "[$DATE] Done. View at http://localhost:8765"
