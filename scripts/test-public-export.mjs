#!/usr/bin/env node
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { once } from 'node:events';
import http from 'node:http';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';

const root = path.resolve(import.meta.dirname, '..');
const temporary = mkdtempSync(path.join(tmpdir(), 'chat-backup-public-'));
const archive = path.join(temporary, 'archive');
const fixture = path.join(temporary, 'fixture.zip');
const badFixture = path.join(temporary, 'unsafe.zip');
const missingDb = path.join(temporary, 'missing.sqlite');
const signal = path.join(temporary, 'signal');

const request = (url) => new Promise((resolve, reject) => {
  const pending = http.get(url, (response) => {
    response.resume();
    response.once('end', () => resolve(response));
  });
  pending.once('error', reject);
});

const startServer = async (directory) => {
  const server = spawn('/usr/bin/python3', ['scripts/serve-local.py', '--directory', directory, '--port', '0'], {
    cwd: root,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let output = '';
  const port = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error(`local server did not start: ${output}`)), 10_000);
    server.stdout.on('data', (chunk) => {
      output += chunk;
      const match = output.match(/127\.0\.0\.1:(\d+)/);
      if (match) {
        clearTimeout(timeout);
        resolve(Number(match[1]));
      }
    });
    server.once('error', (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    server.once('exit', (code) => {
      clearTimeout(timeout);
      reject(new Error(`local server exited early (${code}): ${output}`));
    });
  });
  return { server, port };
};

const stopServer = async (server) => {
  if (server.exitCode === null) {
    const exited = once(server, 'exit');
    server.kill('SIGTERM');
    await exited;
  }
};

const makeZip = (file, members) => {
  const script = [
    'import json, sys, zipfile',
    'with zipfile.ZipFile(sys.argv[1], "w") as archive:',
    '    for name, content in json.loads(sys.argv[2]).items():',
    '        archive.writestr(name, content)',
  ].join('\n');
  const run = spawnSync('/usr/bin/python3', ['-c', script, file, JSON.stringify(members)], { encoding: 'utf8' });
  if (run.status !== 0) throw new Error(`Could not build synthetic ZIP: ${run.stderr || run.error?.message}`);
};

const build = (exportPath, database = missingDb, includeLocal = false) => spawnSync('/usr/bin/python3', ['chat_backup/builder.py'], {
  cwd: root,
  encoding: 'utf8',
  timeout: 120_000,
  env: {
    ...process.env,
    CHAT_BACKUP_DIR: archive,
    CHAT_BACKUP_SIGNAL_DIR: signal,
    CHAT_BACKUP_WA_BASE: path.join(temporary, 'whatsapp'),
    CHAT_BACKUP_WA_DB: database,
    CHAT_BACKUP_WA_EXPORTS: exportPath,
    CHAT_BACKUP_INCLUDE_LOCAL: includeLocal ? '1' : '',
  },
});

try {
  mkdirSync(path.join(signal, 'messages'), { recursive: true });
  writeFileSync(path.join(signal, 'messages', 'unrelated.txt'), [
    'Conversation: Local source',
    'From: Local',
    'Sent: Thu, 01 Jan 2026 12:00:00',
    'unrelated message one',
    'From: Local',
    'Sent: Thu, 01 Jan 2026 12:01:00',
    'unrelated message two',
  ].join('\n'));
  mkdirSync(archive, { recursive: true });
  writeFileSync(path.join(archive, 'index.html'), `const D=${JSON.stringify(JSON.stringify([{
    id: 'old', name: 'Previous local archive', source: 'WhatsApp', entries: [],
  }]))};\nconst C=`);

  const filename = 'odd "?#.jpg';
  const activeFilename = 'untrusted.html';
  makeZip(fixture, {
    '_chat.txt': [
      '[01/01/2026, 12:00:00] Synthetic: </script><script>globalThis.chatBackupInjected=1</script>',
      `[01/01/2026, 12:00:01] Synthetic: <attached: ${filename}>`,
      `[01/01/2026, 12:00:02] Synthetic: <attached: ${activeFilename}>`,
    ].join('\n'),
    [filename]: 'synthetic image bytes',
    [activeFilename]: '<script>globalThis.attachmentExecuted = true</script>',
  });

  const first = build(fixture);
  assert.equal(first.status, 0, first.stderr || first.error?.message);
  const index = path.join(archive, 'index.html');
  const media = path.join(archive, 'media', 'whatsapp', 'wa_export_fixture', filename);
  const activeMedia = path.join(archive, 'media', 'whatsapp', 'wa_export_fixture', activeFilename);
  const html = readFileSync(index, 'utf8');
  assert.equal((html.match(/<\/script>/gi) ?? []).length, 1, 'message text closed a script element');
  assert.ok(!html.includes('<script>globalThis.chatBackupInjected=1</script>'));
  const encoded = html.split('const D=')[1]?.split(';\nconst C=')[0];
  const conversations = JSON.parse(JSON.parse(encoded));
  assert.equal(conversations[0].entries[0].text, '</script><script>globalThis.chatBackupInjected=1</script>');
  assert.ok(existsSync(media), 'quoted fixture media was not exported');
  assert.ok(existsSync(activeMedia), 'synthetic active attachment was not exported');
  assert.ok(!conversations.some((conversation) => ['Local source', 'Previous local archive'].includes(conversation.name)), 'manual export mixed in owner-local data');

  const generatedScript = html.match(/<script>([\s\S]*)<\/script>/)?.[1];
  assert.ok(generatedScript, 'viewer script was not generated');
  const syntax = spawnSync(process.execPath, ['--check'], { input: generatedScript, encoding: 'utf8' });
  assert.equal(syntax.status, 0, syntax.stderr || 'viewer script did not parse');

  const localServer = readFileSync(path.join(root, 'scripts', 'serve-local.py'), 'utf8');
  assert.match(localServer, /\("127\.0\.0\.1", args\.port\)/, 'viewer server is not locked to loopback');
  assert.ok(!html.includes('fonts.googleapis.com'), 'viewer still loads remote fonts');
  const { server, port } = await startServer(archive);
  try {
    const response = await request(`http://127.0.0.1:${port}/media/whatsapp/wa_export_fixture/${activeFilename}`);
    assert.equal(response.headers['x-content-type-options'], 'nosniff');
    assert.equal(response.headers['content-disposition'], 'attachment');
    assert.match(response.headers['content-security-policy'] ?? '', /sandbox/);
  } finally {
    await stopServer(server);
  }

  const mediaUrlSource = html.match(/function mediaUrl\(path\)\{.*?\}/)?.[0];
  assert.ok(mediaUrlSource, 'viewer does not define media URL validation');
  const mediaUrl = new Function(`${mediaUrlSource}; return mediaUrl;`)();
  assert.equal(mediaUrl('javascript:alert(1)'), null);
  assert.equal(mediaUrl('https://example.test/attachment.jpg'), null);
  assert.equal(mediaUrl('media/../attachment.jpg'), null);
  assert.equal(mediaUrl(`media/whatsapp/fixture/${filename}`), 'media/whatsapp/fixture/odd%20%22%3F%23.jpg');

  const escapedAttachment = path.join(signal, 'outside', 'secret.txt');
  mkdirSync(path.dirname(escapedAttachment), { recursive: true });
  writeFileSync(escapedAttachment, 'synthetic local-only content');
  writeFileSync(path.join(signal, 'messages', 'traversal.txt'), [
    'Conversation: ../outside',
    'From: Synthetic',
    'Sent: Thu, 01 Jan 2026 12:00:00',
    'first synthetic message',
    'From: Synthetic',
    'Sent: Thu, 01 Jan 2026 12:01:00',
    'second synthetic message',
    'Attachment: secret.txt (text/plain, synthetic)',
  ].join('\n'));
  const localArchive = path.join(temporary, 'local-archive');
  const localSource = spawnSync('/usr/bin/python3', ['chat_backup/builder.py'], {
    cwd: root,
    encoding: 'utf8',
    timeout: 120_000,
    env: {
      ...process.env,
      CHAT_BACKUP_DIR: localArchive,
      CHAT_BACKUP_SIGNAL_DIR: signal,
      CHAT_BACKUP_WA_BASE: path.join(temporary, 'whatsapp'),
      CHAT_BACKUP_WA_DB: missingDb,
      CHAT_BACKUP_WA_EXPORTS: '',
      CHAT_BACKUP_INCLUDE_LOCAL: '1',
    },
  });
  assert.equal(localSource.status, 0, localSource.stderr || localSource.error?.message);
  assert.ok(!existsSync(path.join(localArchive, 'media', 'signal', '.._outside', 'secret.txt')), 'local source path escaped its attachment root');

  const previousHtml = readFileSync(index, 'utf8');
  writeFileSync(path.join(temporary, 'broken.sqlite'), 'not a SQLite database');
  const failed = build('', path.join(temporary, 'broken.sqlite'), true);
  assert.notEqual(failed.status, 0, 'synthetic invalid source unexpectedly built');
  assert.equal(readFileSync(index, 'utf8'), previousHtml, 'failed build replaced valid output');
  assert.ok(existsSync(media), 'failed build removed valid media');
  assert.ok(!existsSync(`${archive}.tmp`), 'failed build left a staged archive behind');

  makeZip(badFixture, { '_chat.txt': '[01/01/2026, 12:00:00] Synthetic: one', '../outside.jpg': 'unsafe' });
  const unsafe = build(badFixture);
  assert.notEqual(unsafe.status, 0, 'unsafe ZIP member unexpectedly built');
  assert.equal(readFileSync(index, 'utf8'), previousHtml, 'unsafe ZIP changed valid output');
  assert.ok(!existsSync(`${archive}.tmp`), 'unsafe ZIP left a staged archive behind');
  console.log('PASS: public export safely handles synthetic script text, filenames, media paths, and failed builds.');
} finally {
  rmSync(temporary, { recursive: true, force: true });
}
