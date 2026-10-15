export const PLATFORMS = ['github', 'gitlab'];
export const PLATFORM_NAMES = { github: 'GitHub', gitlab: 'GitLab' };
const statuses = ['complete', 'partial', 'unavailable'];
const colors = ['blue', 'purple', 'green', 'orange'];
const icons = ['cube', 'monitor', 'phone', 'globe'];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function validDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
    && Number.isFinite(Date.parse(`${value}T00:00:00Z`))
    && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
}

export function validateData(data) {
  assert(data?.schemaVersion === 1, 'schemaVersion deve ser 1.');
  assert(validDate(data.week?.start) && validDate(data.week?.end), 'Informe datas válidas no formato AAAA-MM-DD.');
  assert(data.week.start <= data.week.end, 'O início da semana deve anteceder o fim.');
  assert(data.activityMetric === 'changedLines', 'Critério de atividade não suportado: use changedLines.');
  assert(typeof data.demo === 'boolean', 'demo deve ser true ou false.');
  for (const key of PLATFORMS) {
    assert(statuses.includes(data.sources?.[key]?.status), `Informe a cobertura de ${PLATFORM_NAMES[key]}.`);
    assert(typeof data.sources[key].note === 'string', `Informe uma nota de cobertura para ${key}.`);
  }
  assert(Array.isArray(data.projects), 'projects deve ser uma lista.');
  const ids = new Set();
  data.projects.forEach((project, index) => {
    assert(typeof project.id === 'string' && project.id.trim() && !ids.has(project.id), `ID ausente ou duplicado no projeto ${index + 1}.`);
    ids.add(project.id);
    assert(typeof project.name === 'string' && project.name.trim(), `Nome ausente no projeto ${index + 1}.`);
    assert(typeof project.summary === 'string' && project.summary.trim(), `Resumo ausente em ${project.name}.`);
    assert(PLATFORMS.includes(project.platform), `Plataforma inválida em ${project.name}.`);
    assert(data.sources[project.platform].status !== 'unavailable', `${project.name}: fonte indisponível não pode conter atividade observada. Use partial para cobertura incompleta.`);
    for (const field of ['commits', 'added', 'removed']) {
      assert(Number.isSafeInteger(project[field]) && project[field] >= 0, `${project.name}: ${field} deve ser um inteiro não negativo.`);
    }
    assert(project.color === undefined || colors.includes(project.color), `Cor inválida em ${project.name}.`);
    assert(project.icon === undefined || icons.includes(project.icon), `Ícone inválido em ${project.name}.`);
  });
  return data;
}

// Um único ponto de extensão para futuros critérios de atividade.
const metrics = { changedLines: project => project.added + project.removed };

// Maiores restos: os percentuais inteiros fecham exatamente em 100%.
export function percentages(values) {
  const total = values.reduce((sum, value) => sum + value, 0);
  if (!total) return values.map(() => null);
  const exact = values.map(value => value / total * 100);
  const result = exact.map(Math.floor);
  const order = exact.map((value, index) => ({ index, fraction: value - result[index] }))
    .sort((a, b) => b.fraction - a.fraction || a.index - b.index);
  const remainder = 100 - result.reduce((sum, value) => sum + value, 0);
  for (let i = 0; i < remainder; i++) result[order[i].index]++;
  return result;
}

// Preserve integer apportionment while distinguishing tiny activity from zero.
export function formatPercent(value, positive = false) {
  return value === null ? '—' : value === 0 && positive ? '<1%' : `${value}%`;
}

export function buildReport(input) {
  const data = validateData(input);
  const projects = data.projects
    .filter(project => project.commits > 0 || project.added + project.removed > 0)
    .map((project, index) => ({ ...project, volume: metrics[data.activityMetric](project), color: project.color ?? colors[index % colors.length], icon: project.icon ?? icons[index % icons.length] }))
    .sort((a, b) => b.volume - a.volume || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const total = projects.reduce((sum, project) => ({
    added: sum.added + project.added, removed: sum.removed + project.removed,
    volume: sum.volume + project.volume, commits: sum.commits + project.commits
  }), { added: 0, removed: 0, volume: 0, commits: 0 });
  Object.entries(total).forEach(([key, value]) => assert(Number.isSafeInteger(value), `Total de ${key} excede o limite numérico suportado.`));
  const shares = percentages(projects.map(project => project.volume));
  projects.forEach((project, index) => { project.percent = shares[index]; });
  const platforms = PLATFORMS.map(key => {
    const source = data.sources[key];
    const entries = projects.filter(project => project.platform === key);
    return {
      key, name: PLATFORM_NAMES[key], ...source,
      commits: source.status === 'unavailable' ? null : entries.reduce((sum, p) => sum + p.commits, 0),
      volume: source.status === 'unavailable' ? null : entries.reduce((sum, p) => sum + p.volume, 0)
    };
  });
  const platformShares = percentages(platforms.map(platform => platform.commits ?? 0));
  platforms.forEach((platform, index) => { platform.percent = platform.commits === null ? null : platformShares[index]; });
  const partial = platforms.some(platform => platform.status !== 'complete');
  const anySource = platforms.some(platform => platform.status !== 'unavailable');
  const leaders = total.volume ? projects.filter(project => project.volume === projects[0].volume) : [];
  const maxPlatformVolume = Math.max(...platforms.map(platform => platform.volume ?? 0));
  const platformLeaders = maxPlatformVolume ? platforms.filter(platform => platform.volume === maxPlatformVolume) : [];
  return { ...data, projects, total, platforms, partial, anySource, leaders, platformLeaders, activeCount: anySource ? projects.length : null };
}

export function formatWeek(week) {
  const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
  const [sy, sm, sd] = week.start.split('-');
  const [ey, em, ed] = week.end.split('-');
  if (sy === ey && sm === em) return `${sd}–${ed} ${months[Number(em) - 1]} ${ey}`;
  if (sy === ey) return `${sd} ${months[Number(sm) - 1]}–${ed} ${months[Number(em) - 1]} ${ey}`;
  return `${sd} ${months[Number(sm) - 1]} ${sy}–${ed} ${months[Number(em) - 1]} ${ey}`;
}
