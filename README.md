# Chat Backup

Exports WhatsApp messages from your Mac into a beautiful, browsable HTML viewer
with inline voice messages, images, and video — themed after heartkemy.art.

Also picks up iPhone exports from WhatsApp's "Export Chat" feature.

## Quick Start

```bash
./run.sh
```

Open http://localhost:8080

## What It Backs Up

| Source | Messages | Voice Messages | Automatic? |
|--------|----------|---------------|------------|
| WhatsApp (Mac app) | ✅ | ✅ (if cached locally) | ✅ Every hour |
| WhatsApp (iPhone export) | ✅ | ✅ (all of them) | When you add a zip |
| Signal Desktop | ❌ (needs keychain PW) | ❌ | No |

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

### Adding iPhone Exports

Drop WhatsApp export zips in `[redacted-local-path]/` with the original naming convention:
`WhatsApp Chat - Name.zip`. The builder finds them automatically by filename.

## Cron / Automation

An hourly sync is installed as a launchd agent:

```bash
# Install (already done):
cp cron/com.chatbackup.plist [redacted-local-path]/
launchctl load [redacted-local-path]/com.chatbackup.plist

# View logs:
tail -f [redacted-local-path]

# Uninstall:
launchctl unload [redacted-local-path]/com.chatbackup.plist
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
