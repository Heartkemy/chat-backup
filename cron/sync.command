#!/usr/bin/env bash
# Run inside Terminal.app so macOS can reuse Terminal's persistent App Data
# permission instead of issuing a one-hour prompt to the background sync app.
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$DIR/.."
LOG="$DIR/sync.log"
SIGTOP="$HOME/.local/bin/sigtop"
TMP_LOG="$(mktemp -t chatbackup-sync)"
trap 'rm -f "$TMP_LOG"' EXIT

cd "$ROOT"
printf '\n[%s] Chat backup run\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"

mkdir -p signal-export/messages signal-export/attachments
if [[ -x "$SIGTOP" ]]; then
    message_stage="$(mktemp -d "$ROOT/signal-export/.messages.XXXXXX")"
    if "$SIGTOP" export-messages -f text "$message_stage" >"$TMP_LOG" 2>&1; then
        rm -rf signal-export/messages.old
        mv signal-export/messages signal-export/messages.old
        if mv "$message_stage" signal-export/messages; then
            rm -rf signal-export/messages.old
            echo "Signal messages: completed" >> "$LOG"
        else
            mv signal-export/messages.old signal-export/messages
            rm -rf "$message_stage"
            echo "Signal messages: unavailable (preserving the last successful export)" >> "$LOG"
        fi
    else
        rm -rf "$message_stage"
        echo "Signal messages: unavailable (preserving the last successful export)" >> "$LOG"
    fi

    attachments_status=0
    "$SIGTOP" export-attachments -i signal-export/attachments >"$TMP_LOG" 2>&1 || attachments_status=$?
    if [[ "$attachments_status" -eq 0 ]]; then
        echo "Signal attachments: completed" >> "$LOG"
    else
        echo "Signal attachments: completed with unavailable source files skipped" >> "$LOG"
    fi
else
    echo "Signal export: unavailable (missing [redacted-local-path])" >> "$LOG"
fi

: > "$TMP_LOG"
if /usr/bin/python3 chat_backup/builder.py >"$TMP_LOG" 2>&1; then
    # Keep operational counts while avoiding names or archive content in logs.
    grep -E '^(Signal:|WhatsApp \(Mac\):|Written:|Conversations:|Total messages:|Audio files \(voice msgs\):|Total media files:)' "$TMP_LOG" >> "$LOG" || true
    echo "Chat archive build: completed" >> "$LOG"
else
    echo "Chat archive build: failed; existing archive preserved" >> "$LOG"
    exit 1
fi
