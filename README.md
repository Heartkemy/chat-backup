# Chat Backup

Exports WhatsApp (and optionally Signal) messages to a browsable HTML viewer
with inline voice messages, images, and video.

## Usage

```bash
./run.sh
```

Open http://localhost:8080 to browse.

## What it backs up

- **WhatsApp (Mac)**: Reads the macOS Catalyst app's `ChatStorage.sqlite` directly.
- **WhatsApp (iPhone)**: Place exported `.zip` files from WhatsApp's "Export Chat"
  feature into `[redacted-local-path] Chat - Name.zip`. The builder picks them up
  automatically.
- **Signal**: Skipped by default (requires macOS Keychain access).

## Output

HTML + media files go to `data/` (or `$CHAT_BACKUP_DIR`).

## Cron

Installed via launchd — runs every hour. See `cron/` for the plist.
