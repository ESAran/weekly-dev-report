import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { buildReport, percentages, formatWeek } from '../model.js';

const demo = JSON.parse(await readFile(new URL('../data/demo.json', import.meta.url), 'utf8'));
const fresh = () => structuredClone(demo);

test('exemplo: totais, participações e líderes são coerentes', () => {
  const result = buildReport(fresh());
  assert.deepEqual(result.total, { added: 842, removed: 391, volume: 1233, commits: 27 });
  assert.deepEqual(result.projects.map(p => p.percent), [41, 32, 18, 9]);
  assert.deepEqual(result.platforms.map(p => [p.commits, p.percent, p.volume]), [[16, 59, 733], [11, 41, 500]]);
  assert.equal(result.leaders[0].name, 'LLM Benchmark');
  assert.equal(result.activeCount, 4);
  assert.equal(result.platformLeaders[0].key, 'github');
});

test('arredondamento soma 100 e denominador zero não inventa participação', () => {
  assert.deepEqual(percentages([1, 1, 1]), [34, 33, 33]);
  assert.deepEqual(percentages([0, 0]), [null, null]);
});

test('cobertura completa sem atividade é zero; fonte indisponível é desconhecida', () => {
  const data = fresh();
  data.projects = data.projects.filter(p => p.platform === 'github');
  assert.equal(buildReport(data).platforms[1].commits, 0);
  data.sources.gitlab.status = 'unavailable';
  const result = buildReport(data);
  assert.equal(result.platforms[1].commits, null);
  assert.equal(result.platforms[1].percent, null);
  assert.equal(result.partial, true);
});

test('ambas indisponíveis não geram zeros nem projetos ativos confirmados', () => {
  const data = fresh(); data.projects = [];
  data.sources.github.status = data.sources.gitlab.status = 'unavailable';
  const result = buildReport(data);
  assert.equal(result.activeCount, null);
  assert.equal(result.anySource, false);
  assert.deepEqual(result.platforms.map(p => p.volume), [null, null]);
});

test('atividade parcial e commits sem diff não inventam foco', () => {
  const data = fresh(); data.projects = [data.projects[0]];
  data.sources.github.status = 'partial';
  data.projects[0].added = data.projects[0].removed = 0;
  const result = buildReport(data);
  assert.equal(result.activeCount, 1);
  assert.equal(result.projects[0].percent, null);
  assert.deepEqual(result.leaders, []);
});

test('sem atividade, empates, ordenação e mais de quatro projetos', () => {
  const data = fresh();
  data.projects = Array.from({ length: 7 }, (_, i) => ({ ...data.projects[0], id: String(i), added: 1, removed: 0 }));
  assert.equal(buildReport(data).leaders.length, 7);
  data.projects.reverse();
  assert.equal(buildReport(data).projects[0].id, '0');
  data.projects.forEach(p => { p.added = p.removed = p.commits = 0; });
  assert.equal(buildReport(data).activeCount, 0);
});

test('dados inválidos falham com uma mensagem clara', () => {
  const negative = fresh(); negative.projects[0].added = -1;
  assert.throws(() => buildReport(negative), /inteiro não negativo/);
  const duplicate = fresh(); duplicate.projects[1].id = duplicate.projects[0].id;
  assert.throws(() => buildReport(duplicate), /duplicado/);
  const unavailable = fresh(); unavailable.sources.github.status = 'unavailable';
  assert.throws(() => buildReport(unavailable), /indisponível/);
  const date = fresh(); date.week.start = '2026-02-30';
  assert.throws(() => buildReport(date), /datas válidas/);
});

test('datas estáveis em transições de mês e ano', () => {
  assert.equal(formatWeek(demo.week), '07–13 Out 2026');
  assert.equal(formatWeek({ start: '2026-09-29', end: '2026-10-05' }), '29 Set–05 Out 2026');
  assert.equal(formatWeek({ start: '2026-12-29', end: '2027-01-04' }), '29 Dez 2026–04 Jan 2027');
});

test('atividade mínima aparece como <1%, distinta de zero e indisponibilidade', async () => {
  const { formatPercent } = await import('../model.js');
  const data = fresh();
  data.projects = [
    { ...data.projects[0], added: 10000, removed: 0, commits: 1000 },
    { ...data.projects[1], added: 1, removed: 0, commits: 1 },
    { ...data.projects[2], added: 0, removed: 0, commits: 1 }
  ];
  const result = buildReport(data);
  assert.equal(result.projects[1].percent, 0);
  assert.equal(formatPercent(result.projects[1].percent, result.projects[1].volume > 0), '<1%');
  assert.equal(formatPercent(result.projects[2].percent, false), '0%');
  assert.equal(formatPercent(null, false), '—');
  assert.equal(formatPercent(result.platforms[1].percent, result.platforms[1].commits > 0), '<1%');
  assert.equal(result.projects.reduce((sum, p) => sum + p.percent, 0), 100);
});
