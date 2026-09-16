#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/ChatBackupSync.app"
SOURCE_PLIST="$ROOT/cron/com.chatbackup.sync.plist"
INSTALLED_PLIST="$HOME/Library/LaunchAgents/com.chatbackup.sync.plist"
SIGTOP="$HOME/.local/bin/sigtop"
SIGTOP_COMPAT="/opt/homebrew/bin/sigtop"
LABEL="com.chatbackup.sync"
DOMAIN="gui/$(id -u)"

fail() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

[[ -d "$APP" ]] || fail "missing $APP; restore the existing signed app from backup rather than rebuilding it"
[[ -x "$APP/Contents/MacOS/sync" ]] || fail "missing sync executable in $APP"
[[ -x "$SIGTOP" ]] || fail "missing $SIGTOP"
/usr/bin/codesign --verify --deep --strict "$APP" 2>/dev/null || fail "ChatBackupSync.app signature is invalid; do not re-sign it ad hoc"
[[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist")" == "com.chatbackup.syncapp" ]] || fail "unexpected ChatBackupSync.app bundle identifier"
[[ "$(/usr/libexec/PlistBuddy -c 'Print :LSUIElement' "$APP/Contents/Info.plist")" == "true" ]] || fail "ChatBackupSync.app is not configured as a headless agent"
/usr/bin/codesign -d --entitlements :- "$APP" 2>/dev/null | /usr/bin/grep -q 'group.net.whatsapp.WhatsApp.shared' || fail "ChatBackupSync.app is missing its WhatsApp app-group entitlement"
/usr/bin/plutil -lint "$SOURCE_PLIST" >/dev/null
if /usr/bin/grep -q 'Terminal' "$SOURCE_PLIST"; then
    fail "the scheduled sync plist must never launch Terminal"
fi

if [[ -e "$SIGTOP_COMPAT" || -L "$SIGTOP_COMPAT" ]]; then
    [[ -L "$SIGTOP_COMPAT" ]] || fail "$SIGTOP_COMPAT exists and is not the managed compatibility symlink"
    [[ "$(readlink "$SIGTOP_COMPAT")" == "$SIGTOP" ]] || fail "$SIGTOP_COMPAT points somewhere unexpected"
else
    /bin/ln -s "$SIGTOP" "$SIGTOP_COMPAT"
fi

/bin/mkdir -p "$HOME/Library/LaunchAgents"
/bin/cp "$SOURCE_PLIST" "$INSTALLED_PLIST"
/usr/bin/plutil -lint "$INSTALLED_PLIST" >/dev/null
/bin/launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
/bin/launchctl bootstrap "$DOMAIN" "$INSTALLED_PLIST"
/bin/launchctl enable "$DOMAIN/$LABEL"

"$ROOT/scripts/check-sync-agent.sh"
printf 'Installed %s with the headless ChatBackupSync.app path.\n' "$LABEL"
printf 'Run /bin/launchctl kickstart %s/%s for a fresh sync.\n' "$DOMAIN" "$LABEL"
