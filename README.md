# Chat Backup

Experimental local exporter for chat archives. It produces a static HTML viewer
and copied media on your machine; it is not a hosted service.

## Safety and status

- The generated archive is unencrypted and can contain sensitive messages and
  media. Keep it on a device you trust.
- Serve it only through the supplied loopback command. It has no authentication
  and must not be exposed to a LAN or the public internet.
- The supported public workflow is a manual WhatsApp ZIP export. It uses only
  Python's standard library and explicitly supplied local paths.
- Existing macOS database, Signal, and scheduled-sync integrations are
  owner-local and experimental. A fresh clone cannot reproduce the signed sync
  app or its macOS privacy grants.
- This current-tree cleanup does not rewrite old Git commits. Historical
  exposure, if any, requires separate remediation.

## Manual export

Use a WhatsApp export ZIP that you control. Do not commit it or the generated
output.

```bash
export CHAT_BACKUP_WA_EXPORTS="/absolute/path/to/your-export.zip"
export CHAT_BACKUP_DIR="$PWD/data"
python3 chat_backup/builder.py
```

`CHAT_BACKUP_WA_EXPORTS` accepts multiple paths separated by your platform's
path separator. This explicit manual path ignores local database and Signal
sources unless you set `CHAT_BACKUP_INCLUDE_LOCAL=1`. The exporter refuses
unsafe archive members and leaves the previous valid output in place if a build
fails.

Serve the resulting archive on loopback only:

```bash
./scripts/serve-local.sh
# http://127.0.0.1:8765
```

The server binds to `127.0.0.1` and does not provide encryption or access
control. Stop it when you finish viewing the archive.

## Local configuration

All inputs are local environment variables; keep values in an ignored `.env`
file or your shell configuration, never in this repository.

| Variable | Purpose |
| --- | --- |
| `CHAT_BACKUP_DIR` | Generated archive directory; defaults to `data/` in this clone. |
| `CHAT_BACKUP_WA_EXPORTS` | Explicit WhatsApp ZIP path or paths for manual export. |
| `CHAT_BACKUP_WA_DB` / `CHAT_BACKUP_WA_BASE` | Optional macOS WhatsApp database and media location. |
| `CHAT_BACKUP_SIGNAL_DIR` | Optional Signal text and attachment export directory. |
| `CHAT_BACKUP_SELF_NAME` | Optional local display name rendered as `You`. |
| `CHAT_BACKUP_INCLUDE_LOCAL` | Set to `1` only when intentionally merging owner-local sources with a manual export. |
| `CHAT_BACKUP_PORT` | Loopback viewer port; defaults to `8765`. |

The macOS database and Signal paths are integration details, not a supported
portable backup contract. Their schemas, permissions, and source availability
can change without warning.

## Scheduled sync

An existing owner installation may use a signed `ChatBackupSync.app` and local
launchd configuration. They are not distributed in this repository. Do not
rebuild or re-sign that app casually because that can invalidate macOS privacy
grants. A fresh clone must use the manual export path above. See
[scheduled-sync limitations](docs/scheduled-sync.md).

## Development and verification

Python 3 and Node.js are sufficient for the checked-in tests. They create only
temporary synthetic fixtures; do not run tests against real archives.

```bash
node scripts/test-public-export.mjs
python3 -c 'from pathlib import Path; compile(Path("chat_backup/builder.py").read_text(encoding="utf-8"), "chat_backup/builder.py", "exec")'
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow and
[SECURITY.md](SECURITY.md) for private vulnerability reporting.

## License

The repository's original code is available under the [MIT License](LICENSE).
It does not relicense chat archives, macOS applications, third-party tools, or
their respective terms.
