#!/usr/bin/env node
import { chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const [month, indexFile, stagedData, from = `${month}-01`, through = `${month}-31`] = process.argv.slice(2);
if (!/^\d{4}-\d{2}$/.test(month ?? '') || !indexFile || !stagedData
  || !from.startsWith(`${month}-`) || !through.startsWith(`${month}-`) || from > through) {
  throw new Error('Usage: node scripts/import-history.mjs YYYY-MM OLD_INDEX STAGED_DATA [FROM_DATE THROUGH_DATE]');
}

const html = readFileSync(indexFile, 'utf8');
const encoded = html.split('const D=')[1]?.split(';\nconst C=')[0];
if (!encoded) throw new Error('Historical archive has no embedded conversations.');
const old = JSON.parse(JSON.parse(encoded));
const root = path.resolve(import.meta.dirname, '../recovered-history');
const target = path.join(root, month);
if (existsSync(target)) throw new Error('Historical month already imported; keep the existing copy.');
mkdirSync(root, { recursive: true, mode: 0o700 });
chmodSync(root, 0o700);
const temporary = mkdtempSync(path.join(root, `.${month}-`));
let mediaFiles = 0, messages = 0;

try {
  const conversations = old.filter((c) => c.source === 'WhatsApp').map((c) => ({
    name: c.name,
    entries: c.entries.filter((e) => e.ts?.slice(0, 10) >= from && e.ts?.slice(0, 10) <= through).map((e) => {
      messages++;
      return { ...e, media: (e.media ?? []).map((m) => {
        if (!m.path) return m;
        const original = m.path;
        if (!original.startsWith('media/') || original.split('/').some((part) => !part || part === '.' || part === '..')) {
          throw new Error('Unsafe historical media path.');
        }
        const recovered = `media/history/${month}/${original.slice(6)}`;
        const destination = path.join(temporary, recovered);
        if (!existsSync(destination)) {
          mkdirSync(path.dirname(destination), { recursive: true, mode: 0o700 });
          copyFileSync(path.join(stagedData, original), destination);
          chmodSync(destination, 0o600);
          mediaFiles++;
        }
        return { ...m, path: recovered };
      }) };
    }),
  })).filter((c) => c.entries.length);
  if (!messages) throw new Error('No WhatsApp messages found for the selected month.');
  writeFileSync(path.join(temporary, 'conversations.json'), JSON.stringify({ month, from, through, conversations }), { mode: 0o600 });
  renameSync(temporary, target);
  console.log(JSON.stringify({ month, conversations: conversations.length, messages, mediaFiles }));
} catch (error) {
  rmSync(temporary, { recursive: true, force: true });
  throw error;
}
