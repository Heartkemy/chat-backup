# Scheduled chat sync: permanent headless path

## Invariant

`com.chatbackup.sync` must launch the existing signed `ChatBackupSync.app` through
LaunchServices. It must never open `cron/sync.command` in Terminal.

The app is an `LSUIElement` agent with the stable bundle ID
`com.chatbackup.syncapp`. Its Apple Development signature and WhatsApp app-group
entitlement give macOS a stable responsible-process identity. The launch plist
also declares `AssociatedBundleIdentifiers` so privacy grants stay attributed to
that bundle.

Do not rebuild or ad-hoc re-sign `ChatBackupSync.app`. That changes the identity
used by macOS privacy controls and can bring back hourly permission prompts. The
current app is intentionally ignored by Git and preserved by the machine backup.

## Why `/opt/homebrew/bin/sigtop` exists

The preserved signed app contains the historical absolute sigtop path
`/opt/homebrew/bin/sigtop`. The current executable is restored at
`[redacted-local-path]`. Installation therefore maintains a compatibility symlink
from the historical path to the current executable. Do not replace the signed app
just to change this path.

## Repair

From the repository root:

```bash
./scripts/install-sync-agent.sh
./scripts/check-sync-agent.sh
```

The installer validates the existing app identity and entitlement, restores the
sigtop compatibility link, installs the canonical plist, and reloads launchd. It
refuses to install a plist that mentions Terminal.

If macOS asks to access other app data again, open **System Settings → Privacy &
Security → Full Disk Access**, locate this exact existing app, and toggle it back
on:

```text
[redacted-local-path]
```

Then run the installer again. A privacy grant cannot be scripted safely. Do not
work around it by switching the hourly job to Terminal.

## Safe verification

```bash
./scripts/check-sync-agent.sh
launchctl kickstart gui/$(id -u)/com.chatbackup.sync
```

Verify using file timestamps, counts, exit state, and hashes only. Do not print
conversation names, message text, attachment paths, or archive contents. A
successful scheduled run must leave Terminal's window count unchanged.

The manual `cron/sync.command` remains a diagnostic fallback. It is not the
scheduled production path.
