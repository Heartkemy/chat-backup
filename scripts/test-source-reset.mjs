#!/usr/bin/env node
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const root = path.resolve(import.meta.dirname, '..');
const temporary = mkdtempSync(path.join(tmpdir(), 'chat-archive-reset-'));
const archive = path.join(temporary, 'archive');
const media = 'media/whatsapp/reset-test/one.bin';
try {
  mkdirSync(path.join(archive, path.dirname(media)), { recursive: true });
  writeFileSync(path.join(archive, media), 'test attachment');
  const conversation = { id: 'old-reset-test', name: 'Reset Test', source: 'WhatsApp', entries: [
    { ts: '2026-09-12 12:00:00', sender: 'Test', text: 'archived before reset', media: [{ path: media, contentType: 'application/octet-stream' }] },
  ] };
  writeFileSync(path.join(archive, 'index.html'), `const D=${JSON.stringify(JSON.stringify([conversation]))};\nconst C=`);
  for (let attempt = 0; attempt < 2; attempt++) {
    const run = spawnSync('/usr/bin/python3', ['chat_backup/builder.py'], {
      cwd: root, encoding: 'utf8', timeout: 120_000,
      env: { ...process.env, CHAT_BACKUP_DIR: archive, CHAT_BACKUP_WA_DB: path.join(temporary, 'reset.sqlite') },
    });
    if (run.status !== 0) throw new Error(`Reset simulation failed on run ${attempt + 1}: ${run.stderr.split('\n').at(-2) ?? run.error?.message}`);
    const html = readFileSync(path.join(archive, 'index.html'), 'utf8');
    const saved = JSON.parse(JSON.parse(html.split('const D=')[1].split(';\nconst C=')[0]));
    const messages = saved.filter((c) => c.name === 'Reset Test' && c.source === 'WhatsApp').flatMap((c) => c.entries);
    if (messages.length !== 1 || messages[0].text !== 'archived before reset' || !existsSync(path.join(archive, media))) {
      throw new Error(`Archived message or media was lost on run ${attempt + 1}`);
    }
  }
  console.log('PASS: archived message and media survive two rebuilds after source reset.');
} finally {
  rmSync(temporary, { recursive: true, force: true });
}
