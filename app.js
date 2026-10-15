import { buildReport, formatWeek, formatPercent, PLATFORM_NAMES } from './model.js';
import { icon } from './icons.js';

const number = value => value === null ? '—' : String(value).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const escape = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const percent = (value, positive = false) => escape(formatPercent(value, positive));
const badge = platform => `<span class="platform-badge">${icon(platform)}<span>${PLATFORM_NAMES[platform]}</span></span>`;
const sectionTitle = (name, title, detail = '') => `<div class="section-heading">${icon(name)}<h2>${title}</h2>${detail ? `<span class="section-detail">${detail}</span>` : ''}</div>`;
const commitText = platform => platform.commits === null ? 'Sem acesso à fonte' : `${number(platform.commits)} ${platform.commits === 1 ? 'commit' : 'commits'}${platform.status === 'partial' ? ' observados' : ''}`;

function render(data) {
  const report = buildReport(data);
  const { projects, total, platforms, leaders, platformLeaders, partial, anySource } = report;
  const focus = leaders.length === 1 ? escape(leaders[0].name) : leaders.length > 1 ? 'Foco compartilhado' : 'Sem alterações';
  const leadPlatform = platformLeaders.length ? platformLeaders.map(p => p.name).join(' e ') : 'Sem alterações';
  const coverage = platforms.filter(p => p.status !== 'complete').map(p => `${p.name}: ${p.status === 'unavailable' ? 'sem acesso à fonte' : 'cobertura parcial'}${p.note ? ` — ${p.note}` : ''}`).join(' • ');
  document.querySelector('#report').innerHTML = `
    <header class="report-header">
      <div class="heading-copy"><h1>Resumo Semanal de Projetos</h1>
        <p class="date">${formatWeek(report.week)}${report.demo ? ' <span>•</span> Dados fictícios' : ''}${partial ? ' <span>•</span> Cobertura parcial' : ''}</p>
      </div>
      <div class="analytics-label">${icon('bars')}<span>Painel analítico</span></div>
    </header>

    <section class="metrics" aria-label="Indicadores principais">
      <article class="metric-card active-card">${icon('layers', 'blue')}<h2>Projetos ativos</h2><strong class="metric-number">${number(report.activeCount)}</strong>${partial && anySource ? '<small class="metric-note">observados</small>' : ''}</article>
      <article class="metric-card focus-card">${icon('target', 'green')}<h2>Maior foco</h2><strong class="focus-name">${anySource ? focus : 'Sem dados'}</strong><p class="focus-percent">${leaders.length ? `<b>${percent(leaders[0].percent, leaders[0].volume > 0)}</b> ${leaders.length > 1 ? 'por projeto líder' : 'da atividade'}` : '— da atividade'}</p></article>
      <article class="metric-card changes-card">${icon('code', 'purple')}<h2>Alterações</h2><strong class="changes-number"><span class="green">${anySource ? '+' + number(total.added) : '—'}</span><span class="slash"> / </span><span class="red">${anySource ? '-' + number(total.removed) : '—'}</span></strong><p>linhas${partial && anySource ? ' observadas' : ''}</p></article>
      <article class="metric-card commits-card">${icon('branch', 'pale')}<h2>Commits</h2><strong class="metric-number">${anySource ? number(total.commits) : '—'}</strong><p class="commits-detail">${platforms.map(p => `${p.name} ${p.commits === null ? '—' : number(p.commits)}${p.status === 'partial' ? '*' : ''}`).join(' • ')}</p></article>
    </section>

    <section class="panel progress-panel" aria-labelledby="progress-title">
      ${sectionTitle('bars', '<span id="progress-title">Andamento dos projetos</span>', 'adições + remoções')}
      <table class="project-table">
        <caption>Participação nas linhas adicionadas + removidas${partial ? ' observadas' : ''}; não representa tempo ou esforço.</caption>
        <colgroup><col class="col-project"><col class="col-platform"><col class="col-focus"><col class="col-lines"><col class="col-commits"></colgroup>
        <thead><tr><th scope="col">Projeto</th><th scope="col">Plataforma</th><th scope="col" title="Participação nas linhas adicionadas + removidas">Foco %</th><th scope="col">Alterações</th><th scope="col">Commits</th></tr></thead>
        <tbody>${projects.map(project => `<tr>
          <th scope="row">${escape(project.name)}</th>
          <td><span class="platform-inline">${icon(project.platform)}<span>${PLATFORM_NAMES[project.platform]}</span></span></td>
          <td><div class="project-share"><strong>${percent(project.percent, project.volume > 0)}</strong><div class="progress-track" role="img" aria-label="${project.percent === null ? 'Sem volume de alterações' : percent(project.percent, project.volume > 0) + ' do volume de alterações'}"><span class="fill ${project.color}" style="width:${(project.percent === 0 && project.volume > 0 ? project.volume / total.volume * 100 : project.percent) ?? 0}%"></span></div></div></td>
          <td class="lines-cell">${number(project.volume)} <span>${project.volume === 1 ? 'linha' : 'linhas'}</span></td><td class="commit-cell">${number(project.commits)}</td>
        </tr>`).join('')}</tbody>
      </table>
      ${projects.length ? '' : `<p class="empty-state">${anySource ? 'Nenhum projeto com atividade nas fontes consultadas.' : 'As fontes estão indisponíveis. Não é possível confirmar a atividade.'}</p>`}
    </section>

    <section class="panel distribution-panel" aria-labelledby="distribution-title">
      ${sectionTitle('pie', '<span id="distribution-title">Distribuição por plataforma</span>', partial ? 'commits observados' : 'por commits')}
      <div class="platform-bar" role="img" aria-label="${platforms.map(p => `${p.name}: ${p.percent === null ? 'participação indisponível' : percent(p.percent, p.commits > 0)}`).join('; ')}">
        ${platforms.map(p => `<span class="platform-segment ${p.key}" style="width:${(p.percent === 0 && p.commits > 0 ? p.commits / total.commits * 100 : p.percent) ?? 0}%"></span>`).join('')}
      </div>
      <div class="platform-totals">${platforms.map(p => `<div class="platform-total">${icon(p.key)}<div class="platform-copy"><div><strong>${p.name}</strong><b>${percent(p.percent, p.commits > 0)}</b></div><p>${commitText(p)}</p></div></div>`).join('')}</div>
    </section>

    <section class="panel summary-panel" aria-labelledby="summary-title">
      ${sectionTitle('document', '<span id="summary-title">Resumo dos projetos</span>')}
      <div class="summary-list">${projects.map(project => `<article class="summary-row">
        ${icon(project.icon, `project-icon ${project.color}`)}<h3>${escape(project.name)}</h3>${badge(project.platform)}
        <p class="summary-text"><span class="summary-dot ${project.color}"></span><span>${escape(project.summary)}</span></p>${icon('chevron', 'chevron')}
      </article>`).join('')}</div>
      ${projects.length ? '' : '<p class="empty-state">Nenhum resumo de atividade disponível.</p>'}
    </section>

    <section class="panel quick-panel" aria-labelledby="quick-title">
      ${sectionTitle('bulb', '<span id="quick-title">Leitura rápida</span>')}
      <div class="quick-grid">
        <div class="quick-item">${icon('target')}<p>Foco principal<br>da semana:<br><strong>${anySource ? focus : 'Sem dados'}</strong></p></div>
        <div class="quick-item">${icon('bars')}<p>Maior volume<br>de alterações no<br><strong>${anySource ? leadPlatform : 'Sem dados'}</strong></p></div>
        <div class="quick-item">${icon('people')}<p>${report.activeCount === null ? 'Fontes de dados<br><strong>indisponíveis</strong>' : `Atividade distribuída<br>em <strong>${number(report.activeCount)} ${report.activeCount === 1 ? 'projeto' : 'projetos'}</strong>`}</p></div>
      </div>
      ${partial ? `<p class="coverage-note">${escape(coverage)}. Totais e participações consideram somente os dados disponíveis.</p>` : ''}
    </section>`;
  const root = document.querySelector('#report');
  root.setAttribute('aria-busy', 'false');
  return report;
}

window.reportReady = (async () => {
  try {
    const file = new URLSearchParams(location.search).get('data') || 'data/demo.json';
    const response = await fetch(file, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Não foi possível carregar o JSON (HTTP ${response.status}).`);
    const report = render(await response.json());
    await document.fonts.ready;
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    document.documentElement.dataset.ready = 'true';
    return { ok: true, projectCount: report.projects.length };
  } catch (error) {
    const root = document.querySelector('#report');
    root.innerHTML = `<h1>Não foi possível gerar o relatório</h1><p role="alert">${escape(error.message)}</p>`;
    root.setAttribute('aria-busy', 'false');
    document.documentElement.dataset.ready = 'error';
    return { ok: false, error: error.message };
  }
})();
