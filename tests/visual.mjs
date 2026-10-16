import assert from 'node:assert/strict';
import { readFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { exportReport } from '../scripts/export.mjs';
import { startServer } from '../scripts/server.mjs';
import { chromium } from 'playwright';

const demo = JSON.parse(await readFile(new URL('../data/demo.json', import.meta.url), 'utf8'));
const directory = await mkdtemp(join(tmpdir(), 'weekly-report-'));
const channel = process.env.PLAYWRIGHT_CHANNEL || 'chrome';
const hash = buffer => createHash('sha256').update(buffer).digest('hex');
try {
  const first = await exportReport({ data: demo, output: join(directory, 'first.png'), scale: 1, channel });
  const second = await exportReport({ data: demo, output: join(directory, 'second.png'), scale: 1, channel });
  assert.equal(hash(await readFile(first.output)), hash(await readFile(second.output)), 'Exportações idênticas devem produzir PNGs idênticos.');
  for (const count of [0, 1, 2, 3, 4, 7]) {
    const data = structuredClone(demo);
    data.projects = Array.from({ length: count }, (_, i) => ({ ...demo.projects[i % 4], id: `project-${i}` }));
    const result = await exportReport({ data, output: join(directory, `projects-${count}.png`), scale: 1, channel });
    if (count === 7) assert.ok(result.height > first.height, 'A altura precisa crescer com mais projetos.');
  }
  const tiny = structuredClone(demo);
  tiny.projects = [
    { ...demo.projects[0], added: 10000, removed: 0, commits: 1000 },
    { ...demo.projects[1], added: 1, removed: 0, commits: 1 },
    { ...demo.projects[2], added: 0, removed: 0, commits: 1 }
  ];
  await exportReport({ data: tiny, output: join(directory, 'tiny.png'), scale: 1, channel });
  const service = await startServer({ data: tiny });
  let browser;
  try {
    browser = await chromium.launch({ headless: true, ...(channel && channel !== 'chromium' ? { channel } : {}) });
    const page = await browser.newPage({ viewport: { width: 942, height: 1672 } });
    await page.goto(service.url + '/?data=/__report-data.json');
    assert.equal((await page.evaluate(() => window.reportReady)).ok, true);
    assert.deepEqual(await page.locator('.project-share strong').allTextContents(), ['100%', '<1%', '0%']);
    assert.equal(await page.locator('.lines-cell').nth(1).textContent(), '1 linha');
    assert.equal(await page.locator('.platform-total').nth(1).locator('b').textContent(), '<1%');
    const tinyWidth = await page.locator('.progress-track .fill').nth(1).evaluate(el => parseFloat(el.style.width));
    assert.ok(tinyWidth > 0 && tinyWidth < 1);
    assert.ok(await page.locator('.project-share strong').nth(1).evaluate(el => el.scrollWidth <= el.clientWidth + 2));
    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= 390));
  } finally {
    if (browser) await browser.close();
    await service.close();
  }
  const long = structuredClone(demo);
  long.projects[0].name = 'Plataforma de avaliação e observabilidade de modelos';
  long.projects[0].summary = 'Revisão dos cenários de avaliação, correções na coleta de métricas e melhorias de navegação para a equipe responsável pelo acompanhamento dos resultados semanais.';
  await exportReport({ data: long, output: join(directory, 'long.png'), scale: 1, channel });
  const partial = structuredClone(demo);
  partial.projects = partial.projects.filter(p => p.platform === 'github');
  partial.sources.gitlab = { status: 'unavailable', note: 'Fonte não consultada neste período.' };
  await exportReport({ data: partial, output: join(directory, 'partial.png'), scale: 1, channel });
  partial.projects = [];
  partial.sources.github.status = 'unavailable';
  await exportReport({ data: partial, output: join(directory, 'unavailable.png'), scale: 1, channel });
  console.log('OK: PNG determinístico, 0–4 e 7 projetos, atividade <1%, textos longos, cobertura incompleta e fontes indisponíveis.');
} finally {
  await rm(directory, { recursive: true, force: true });
}
