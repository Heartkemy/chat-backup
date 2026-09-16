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
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

/usr/bin/plutil -lint "$SOURCE_PLIST" >/dev/null || fail "repository plist is invalid"
[[ -f "$INSTALLED_PLIST" ]] || fail "installed plist is missing"
/usr/bin/plutil -lint "$INSTALLED_PLIST" >/dev/null || fail "installed plist is invalid"
/usr/bin/cmp -s "$SOURCE_PLIST" "$INSTALLED_PLIST" || fail "installed plist differs from the repository copy"

for plist in "$SOURCE_PLIST" "$INSTALLED_PLIST"; do
    /usr/bin/grep -q 'ChatBackupSync.app' "$plist" || fail "$plist does not launch ChatBackupSync.app"
    ! /usr/bin/grep -q 'Terminal' "$plist" || fail "$plist regressed to a Terminal-owned launch path"
    /usr/bin/grep -q 'AssociatedBundleIdentifiers' "$plist" || fail "$plist is missing TCC attribution metadata"
done

[[ -x "$APP/Contents/MacOS/sync" ]] || fail "headless sync executable is missing"
/usr/bin/codesign --verify --deep --strict "$APP" 2>/dev/null || fail "ChatBackupSync.app signature is invalid"
[[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist")" == "com.chatbackup.syncapp" ]] || fail "unexpected bundle identifier"
[[ "$(/usr/libexec/PlistBuddy -c 'Print :LSUIElement' "$APP/Contents/Info.plist")" == "true" ]] || fail "LSUIElement is not enabled"
/usr/bin/codesign -d --entitlements :- "$APP" 2>/dev/null | /usr/bin/grep -q 'group.net.whatsapp.WhatsApp.shared' || fail "WhatsApp app-group entitlement is missing"

[[ -x "$SIGTOP" ]] || fail "current sigtop executable is missing"
[[ -L "$SIGTOP_COMPAT" ]] || fail "legacy sigtop compatibility symlink is missing"
[[ "$(readlink "$SIGTOP_COMPAT")" == "$SIGTOP" ]] || fail "legacy sigtop compatibility symlink points somewhere unexpected"

loaded="$(/bin/launchctl print "$DOMAIN/$LABEL" 2>/dev/null)" || fail "launchd job is not loaded"
/usr/bin/grep -q 'program = /usr/bin/open' <<<"$loaded" || fail "loaded job does not use LaunchServices"
/usr/bin/grep -q 'ChatBackupSync.app' <<<"$loaded" || fail "loaded job does not target ChatBackupSync.app"
! /usr/bin/grep -q 'Terminal' <<<"$loaded" || fail "loaded job still targets Terminal"

printf 'PASS: headless sync path, stable TCC identity, sigtop path, and loaded launchd job are consistent.\n'
