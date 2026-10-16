import { readFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';
import { startServer, root } from './server.mjs';
import { buildReport } from '../model.js';

export async function exportReport({ input = resolve(root, 'data/demo.json'), output = resolve(root, 'reports/weekly-dev-report.png'), scale = 2, channel = process.env.PLAYWRIGHT_CHANNEL || 'chrome', data } = {}) {
  if (![1, 2, 3].includes(scale)) throw new Error('--scale deve ser 1, 2 ou 3.');
  const payload = data ?? JSON.parse(await readFile(input, 'utf8'));
  buildReport(payload);
  const service = await startServer({ data: payload });
  let browser;
  try {
    browser = await chromium.launch({ headless: true, ...(channel && channel !== 'chromium' ? { channel } : {}) });
    const context = await browser.newContext({
      viewport: { width: 942, height: 1672 }, deviceScaleFactor: scale,
      locale: 'pt-BR', timezoneId: 'UTC', colorScheme: 'dark', reducedMotion: 'reduce',
      serviceWorkers: 'block'
    });
    // A exportação usa apenas os arquivos locais, inclusive a fonte.
    await context.route('**/*', route => new URL(route.request().url()).origin === service.url ? route.continue() : route.abort());
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('requestfailed', request => errors.push(`Falha ao carregar ${request.url()}`));
    await page.goto(`${service.url}/?data=/__report-data.json`, { waitUntil: 'networkidle' });
    const ready = await page.evaluate(() => window.reportReady);
    if (!ready?.ok) throw new Error(ready?.error ?? 'O relatório não concluiu a renderização.');
    if (errors.length) throw new Error(errors.join('\n'));
    const fontLoaded = await page.evaluate(() => document.fonts.check('20px Roboto'));
    if (!fontLoaded) throw new Error('A fonte local Roboto não foi carregada.');
    const overflow = await page.evaluate(() => {
      const root = document.querySelector('#report');
      const bounds = root.getBoundingClientRect();
      return [...root.querySelectorAll('h1,h2,h3,p,td,th,.metric-number,.changes-number,.focus-name,.analytics-label')]
        .filter(element => {
          const rect = element.getBoundingClientRect();
          return rect.left < bounds.left - 1 || rect.right > bounds.right + 1 || element.scrollWidth > element.clientWidth + 2;
        }).map(element => element.textContent.trim());
    });
    if (overflow.length) throw new Error(`Conteúdo excede o espaço disponível: ${overflow.join('; ')}`);
    await mkdir(dirname(output), { recursive: true });
    const report = page.locator('#report');
    const png = await report.screenshot({ path: output, type: 'png', animations: 'disabled', caret: 'hide', scale: 'device' });
    return { output, width: png.readUInt32BE(16), height: png.readUInt32BE(20), browser: browser.version() };
  } finally {
    if (browser) await browser.close();
    await service.close();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    const args = process.argv.slice(2);
    const options = {};
    for (let index = 0; index < args.length; index += 2) {
      const flag = args[index];
      const value = args[index + 1];
      if (!['--input', '--output', '--scale', '--channel'].includes(flag) || !value) throw new Error('Uso: npm run export -- [--input arquivo.json] [--output arquivo.png] [--scale 1|2|3] [--channel chrome|chromium]');
      options[flag.slice(2)] = flag === '--scale' ? Number(value) : flag === '--channel' ? value : resolve(value);
    }
    console.log(JSON.stringify(await exportReport(options), null, 2));
  } catch (error) {
    console.error(`Falha na exportação: ${error.message}`);
    process.exitCode = 1;
  }
}
