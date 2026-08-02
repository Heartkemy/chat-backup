#!/usr/bin/env bash
# Runs the chat backup builder inside Terminal.app, which holds the
# scoped TCC grants for WhatsApp's data and the Downloads folder.
# Opens briefly once per hour, then closes itself.
DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$DIR/.."
/usr/bin/python3 chat_backup/builder.py >> "$DIR/sync.log" 2>&1

# Close only this script's window
osascript -e 'tell app "Terminal" to close (first window whose name contains "sync.command")' > /dev/null 2>&1
