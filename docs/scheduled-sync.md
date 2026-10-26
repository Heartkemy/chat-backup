# Scheduled sync limitations

Scheduled sync is an owner-local experimental integration, not a public
installation path. The reproducible public baseline is the manual export in
the [README](../README.md).

An existing installation may depend on all of the following local state:

- a pre-existing signed `ChatBackupSync.app`;
- an existing macOS privacy grant and WhatsApp app-group access;
- a locally installed `sigtop` executable; and
- a launchd plist containing machine-specific paths.

The signed app, local launchd configuration, and generated archive data are not
distributed in this repository. A fresh clone cannot create or validate the
app or its grants, and it must not claim otherwise. Do not rebuild, ad-hoc
re-sign, or replace an existing signed app merely to make this repository look
portable; that can cause macOS to request permissions again.

When `CHAT_BACKUP_WA_EXPORTS` is set, the public manual-export path excludes
owner-local database and Signal sources unless `CHAT_BACKUP_INCLUDE_LOCAL=1` is
explicitly set. The preserved signed app's internal invocation is not
reproducible or verified from this repository.

If you already own a working local setup, preserve its signed app, installed
launch agent, and privacy grants. Any repair script remains for that local
recovery context only and is not a supported setup command for contributors.
The public workflow is explicit manual export plus `scripts/serve-local.sh`,
which binds only to `127.0.0.1`.
