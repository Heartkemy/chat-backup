# Contributing

Keep changes focused and never commit chat exports, logs, contacts, tokens, or
other personal data.

Before opening a pull request, run the syntax checks used by CI:

```sh
python3 -c 'from pathlib import Path; [compile(path.read_text(encoding="utf-8"), str(path), "exec") for path in Path("chat_backup").rglob("*.py")]'
for file in scripts/*.mjs; do node --check "$file"; done
bash -n run.sh scripts/*.sh
```

Run `python3 -m unittest discover -s tests` and
`node scripts/test-public-export.mjs` for the temporary synthetic fixtures.
Never run backup, sync, install, or export operations against real archives in
CI or review checks.
