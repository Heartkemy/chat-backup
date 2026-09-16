# Chat Backup

Exports WhatsApp messages from your Mac into a beautiful, browsable HTML viewer
with inline voice messages, images, and video — themed after heartkemy.art.

Also picks up iPhone exports from WhatsApp's "Export Chat" feature.

## Quick Start

```bash
./run.sh
```

Open http://localhost:8765

## How It Runs

The viewer server and hourly sync run through launchd:

| Job | What it does |
|-----|-------------|
| `com.chatbackup.server` | Serves the viewer on `127.0.0.1:8765`. `KeepAlive` — auto-restarts on crash and at login. |
| `com.chatbackup.sync` | Opens `cron/sync.command` in Terminal every hour and at login. |

The scheduled command exports a fresh Signal message snapshot, updates Signal
attachments incrementally, and rebuilds the archive atomically. Terminal is
opened without being brought to the foreground and the command window closes
when the run finishes.

### One-time macOS approval

The former `ChatBackupSync.app` path caused macOS App Data grants to expire
after about one hour because its child Python process read another app's
container. The supported path now uses Terminal's stable system identity. If
macOS asks, allow **Terminal** to access WhatsApp/Signal app data and allow the
`sigtop` command to read its saved Signal key. These approvals persist across
scheduled runs.

The sync resolves `sigtop` from `[redacted-local-path]`, so Homebrew changes do
not break message ingestion. Operational logs contain counts and status only,
not conversation names or message content.

RAM/CPU: negligible — the builder runs briefly once per hour.

## What It Backs Up

| Source | Messages | Voice Messages | Automatic? |
|--------|----------|---------------|------------|
| WhatsApp (Mac app) | ✅ | ✅ (if cached locally) | ✅ Every hour |
| WhatsApp (iPhone export) | ✅ | ✅ (all of them) | When you add a zip |
| Signal Desktop | ✅ | ✅ (if cached locally) | ✅ Every hour |

WhatsApp voice messages from the Mac app are limited — the app only caches audio
files it has played locally. For a **complete backup with all voice messages**,
use your iPhone: open a chat → tap the contact name → **Export Chat** (with media).
Place the resulting `.zip` in `[redacted-local-path] Chat - Name.zip` and it'll be
picked up on the next run (or run `./run.sh` manually).

## How It Works

1. **WhatsApp (Mac)** — reads `ChatStorage.sqlite` from the macOS Catalyst app's
   sandbox at `~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/`.
   The database is unencrypted SQLite with CoreData schema.
2. **WhatsApp (iPhone)** — parses WhatsApp's standard `_chat.txt` export format
   and extracts all media files (including `.opus` voice messages).
3. **HTML Viewer** — generates a single-page dark-themed chat browser with:
   - Search by conversation name
   - [redacted-contact] messages
   - Inline audio/video/image playback
   - Image lightbox
   - Gradient heartkemy theme

All media files are copied into the output directory — no external dependencies
at runtime.

## Project Structure

```
chat_backup/
├── chat_backup/
│   └── builder.py         # Main export + HTML generation script
├── cron/
│   ├── com.chatbackup.plist  # launchd job (hourly)
│   └── sync.log / sync.err  # Cron output logs
├── data/                  # Generated output (HTML + media)
│   ├── index.html
│   └── media/
├── run.sh                 # Build and serve
├── .gitignore
└── README.md
```

## Development

### Dependencies

- Python 3
- Standard library only (no pip packages needed)

### Building

```bash
python3 chat_backup/builder.py
```

Output goes to `data/` (override with `$CHAT_BACKUP_DIR`).

### Serving Locally

```bash
cd data && python3 -m http.server 8080
```

Or just use `./run.sh` which does both.

### Signal Export

Signal Desktop encrypts its database key in the macOS Keychain. The keychain
approval was granted once for the `sigtop` tool, and macOS caches it — so the
hourly sync exports Signal automatically, silently, with no prompts.

Note: Signal Desktop only syncs messages to this Mac while the app is open.
If Signal Desktop hasn't been run in a while, the export reflects the last
time it was open. Open Signal Desktop occasionally to keep the archive fresh.

### Adding iPhone Exports

Drop WhatsApp export zips in `[redacted-local-path]/` with the original naming convention:
`WhatsApp Chat - Name.zip`. The builder finds them automatically by filename.

## Cron / Automation

The hourly sync is installed as a launchd agent:

```bash
# Install (already done):
cp cron/com.chatbackup.sync.plist [redacted-local-path]/
launchctl bootstrap gui/$(id -u) [redacted-local-path]

# View redacted operational logs:
tail -f [redacted-local-path]

# Uninstall:
launchctl bootout gui/$(id -u)/com.chatbackup.sync
```

The server at `:8080` survives restarts — the cron job checks if it's running
and starts it if not.


## Design

Themes after [heartkemy.art](https://heartkemy.art) — dark warm background
(`#221a16`), ivory text (`#fff3e3`), alchemical gradient accents
(purple → orange → yellow). Fonts: Outfit (UI) + Bitter (serif accents).

## GitHub

```
https://github.com/iPurpl3x/chat-backup
```
