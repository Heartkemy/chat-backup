#!/usr/bin/env bash
# Runs the chat backup builder inside Terminal.app, which holds the
# scoped TCC grants. The Basic profile's shellExitAction=1 makes the
# window close itself when this script exits — nothing to clean up.
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR/.."
/usr/bin/python3 chat_backup/builder.py >> "$DIR/sync.log" 2>&1
exit 0
