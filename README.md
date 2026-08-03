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

Two launchd jobs run in the background (no terminal needed):

| Job | What it does |
|-----|-------------|
| `com.chatbackup.server` | Serves the viewer on `127.0.0.1:8765`. `KeepAlive` — auto-restarts on crash and at login. |
| `com.chatbackup.sync` | Runs the builder every hour + at login. Launches `ChatBackupSync.app`, a headless compiled app. |

RAM/CPU: negligible — the server is a tiny Python process (~10MB RAM, ~0% CPU when idle). The builder runs ~30s per hour. Nothing to worry about.

### How the sync app bypasses permissions

`ChatBackupSync.app` is a compiled Mach-O binary, ad-hoc signed with the
**`group.net.whatsapp.WhatsApp.shared`** app-group entitlement — the same group
WhatsApp's own container belongs to. macOS therefore lets it read the WhatsApp
database without any TCC permission or prompt. It runs headless
(`LSUIElement`), produces no windows, and needs no approval. No Terminal, no
Full Disk Access, nothing visible. Rebuild notes: the grant is tied to the code
signature, so re-signing the app re-triggers the (silent, group-based) check —
it keeps working as long as the entitlement stays in the signature.

## What It Backs Up

| Source | Messages | Voice Messages | Automatic? |
|--------|----------|---------------|------------|
| WhatsApp (Mac app) | ✅ | ✅ (if cached locally) | ✅ Every hour |
| WhatsApp (iPhone export) | ✅ | ✅ (all of them) | When you add a zip |
| Signal Desktop | ✅ (manual export) | ✅ (if cached locally) | Manual only |

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

### Manual Signal Export

Signal Desktop encrypts its database key in the macOS Keychain and only the
Signal app itself can access it — so it can't be automated. To update Signal
data manually:

1. **Quit Signal** completely
2. Open Terminal and run:

```bash
mkdir -p [redacted-local-path]/messages [redacted-local-path]/attachments
sigtop export-messages -f text [redacted-local-path]/messages
sigtop export-attachments [redacted-local-path]/attachments
```

3. A **keychain dialog** will appear — click **Allow** (enter your Mac password if prompted)
4. Then rebuild the viewer:

```bash
cd [redacted-local-path] && ./run.sh
```

You only need to do this when you want a fresh snapshot of your Signal messages.

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
