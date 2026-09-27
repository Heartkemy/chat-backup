#!/usr/bin/env node
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const [beforeFile, afterFile] = process.argv.slice(2);
if (!beforeFile || !afterFile) throw new Error('Usage: node scripts/check-recovered-history.mjs BEFORE_INDEX AFTER_INDEX');
const read = (file) => {
  const encoded = readFileSync(file, 'utf8').split('const D=')[1]?.split(';\nconst C=')[0];
  if (!encoded) throw new Error('Archive has no embedded conversations.');
  return JSON.parse(JSON.parse(encoded));
};
const key = (name, source, entry) => JSON.stringify([
  source, name, entry.ts, entry.sender, entry.text,
  (entry.media ?? []).map((media) => path.basename(media.path ?? '')).sort(),
]);
const before = read(beforeFile), after = read(afterFile);
const present = new Map();
for (const conversation of after) for (const entry of conversation.entries) {
  const id = key(conversation.name, conversation.source, entry);
  present.set(id, (present.get(id) ?? 0) + 1);
}
const afterKeys = new Set(present.keys());
let lost = 0;
for (const conversation of before) for (const entry of conversation.entries) {
  const id = key(conversation.name, conversation.source, entry);
  const count = present.get(id) ?? 0;
  if (count) present.set(id, count - 1); else lost++;
}
let recovered = 0, missingRecovered = 0, missingMedia = 0;
for (const month of ['2026-07', '2026-08', '2026-09']) {
  const saved = JSON.parse(readFileSync(path.resolve(import.meta.dirname, `../recovered-history/${month}/conversations.json`), 'utf8'));
  for (const conversation of saved.conversations) for (const entry of conversation.entries) {
    recovered++;
    if (!afterKeys.has(key(conversation.name, 'WhatsApp', entry))) missingRecovered++;
    for (const media of entry.media ?? []) if (media.path && !existsSync(path.join(path.dirname(afterFile), media.path))) missingMedia++;
  }
}
const result = { beforeMessages: before.reduce((n, c) => n + c.entries.length, 0), afterMessages: after.reduce((n, c) => n + c.entries.length, 0), recovered, lost, missingRecovered, missingMedia };
console.log(JSON.stringify(result));
if (lost || missingRecovered || missingMedia) process.exitCode = 1;
