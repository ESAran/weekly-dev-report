import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, symlink, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { startServer, root } from '../scripts/server.mjs';

test('HTTP oferece o dashboard, bloqueia configurações e links para arquivos externos', async () => {
  const privateDir = await mkdtemp(join(tmpdir(), 'weekly-private-'));
  const link = join(root, 'data', `symlink-test-${process.pid}.json`);
  const server = await startServer();
  try {
    await writeFile(join(privateDir, 'example.json'), '{"synthetic":true}');
    await symlink(join(privateDir, 'example.json'), link);
    for (const path of ['/', '/styles.css', '/app.js', '/data/demo.json', '/assets/fonts/Roboto.ttf']) {
      assert.equal((await fetch(server.url + path)).status, 200, path);
    }
    for (const path of ['/.env', '/.env.production', '/collector/config.local.json', '/data/config.json',
      '/data/audit.json', '/data/report.json', '/data/custom.local.json', '/reports/private.png',
      '/node_modules/playwright/package.json', '/.git/config', '/%2e%2e%2fREADME.md', `/data/symlink-test-${process.pid}.json`]) {
      assert.equal((await fetch(server.url + path)).status, 403, path);
    }
  } finally {
    await server.close();
    await rm(link, { force: true });
    await rm(privateDir, { recursive: true, force: true });
  }
});
