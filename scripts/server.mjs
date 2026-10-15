import http from 'node:http';
import { readFile, realpath } from 'node:fs/promises';
import { dirname, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

export const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.ttf': 'font/ttf', '.png': 'image/png' };

export async function startServer({ port = 0, data } = {}) {
  const realRoot = await realpath(root);
  const server = http.createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      if (pathname === '/__report-data.json' && data !== undefined) {
        response.writeHead(200, { 'Content-Type': types['.json'], 'Cache-Control': 'no-store' });
        response.end(JSON.stringify(data));
        return;
      }
      const filename = resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname));
      const relative = filename.slice(root.length + 1).split(sep).join('/');
      const runtimeFile = ['index.html', 'styles.css', 'app.js', 'model.js', 'icons.js', 'assets/fonts/Roboto.ttf'].includes(relative);
      const dataFile = /^data\/[\w-]+\.json$/.test(relative) && !/^(?:data\/)(?:audit|report|summaries|config|credentials|secrets|request|run)\.json$/.test(relative);
      if (!filename.startsWith(root + sep) || (!runtimeFile && !dataFile)) {
        response.writeHead(403).end('Forbidden');
        return;
      }
      // A symlink inside data/ must not expose files from a private directory.
      if (!(await realpath(filename)).startsWith(realRoot + sep)) {
        response.writeHead(403).end('Forbidden');
        return;
      }
      const content = await readFile(filename);
      response.writeHead(200, { 'Content-Type': types[extname(filename)] ?? 'application/octet-stream', 'Cache-Control': 'no-store' });
      response.end(content);
    } catch {
      response.writeHead(404).end('Not found');
    }
  });
  await new Promise((resolveReady, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', resolveReady);
  });
  return { server, url: `http://127.0.0.1:${server.address().port}`, close: () => new Promise((resolveClosed, reject) => server.close(error => error ? reject(error) : resolveClosed())) };
}
