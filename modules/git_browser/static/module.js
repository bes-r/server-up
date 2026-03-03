/* ═══════════════════════════════════════════════════════════════════════════
   module_git_browser.js — App Store (git repos met docker stacks)
   ═══════════════════════════════════════════════════════════════════════════ */
'use strict';

const AppStore = (() => {
  let _repos = [];
  let _stacks = [];
  let _searchTimer = null;

  /* ── Render App Store sectie ─────────────────────────────────────────────── */
  async function load() {
    const el = document.getElementById('app-store-content');
    if (!el) return;

    el.innerHTML = `<div class="empty"><span class="mdi mdi-loading mdi-spin"></span><p class="empty-text">Laden…</p></div>`;

    const [repos, stacks] = await Promise.all([
      fetch('/api/repos').then(r => r.json()).catch(() => []),
      fetch('/api/git/stacks').then(r => r.json()).catch(() => ({ stacks: [] })),
    ]);

    _repos  = Array.isArray(repos) ? repos : (repos.repos || []);
    _stacks = stacks.stacks || stacks || [];

    el.innerHTML = _buildHTML();
    _bindEvents();
  }

  function _buildHTML() {
    const repoFilter = _repos.length > 1
      ? `<div class="filter-bar">
          <div class="search-wrap">
            <span class="mdi mdi-magnify"></span>
            <input type="text" class="search-input" id="app-search" placeholder="Zoek stack…">
          </div>
          <select class="search-input" id="app-repo-filter" style="max-width:200px;flex:none">
            <option value="">Alle repositories</option>
            ${_repos.map(r => `<option value="${esc(r.id)}">${esc(r.name)}</option>`).join('')}
          </select>
        </div>`
      : `<div class="filter-bar">
          <div class="search-wrap">
            <span class="mdi mdi-magnify"></span>
            <input type="text" class="search-input" id="app-search" placeholder="Zoek stack…">
          </div>
        </div>`;

    const repoList = _repos.length
      ? _repos.map(r => `
        <div class="repo-row" id="repo-row-${esc(r.id)}">
          <span class="mdi mdi-source-repository repo-icon" style="color:${r.url?'var(--accent)':'var(--warn)'}"></span>
          <div class="repo-info">
            <div class="repo-name">${esc(r.name || r.id)}
              ${!r.url ? `<span style="font-size:10px;color:var(--warn);margin-left:6px">⚠ URL niet ingesteld</span>` : ''}
              ${r.subdir ? `<span style="font-size:10px;color:var(--dim);margin-left:4px">/ ${esc(r.subdir)}</span>` : ''}
            </div>
            <div class="repo-url">${r.url ? esc(r.url) : '<em style="color:var(--warn)">Vul URL in via Instellingen → Git</em>'}</div>
          </div>
          ${r.url ? `<button class="btn btn-sm" onclick="AppStore.pull('${esc(r.id)}')" title="Pull / klonen">
            <span class="mdi mdi-source-pull"></span>
          </button>` : ''}
          <button class="btn btn-sm btn-ghost" onclick="AppStore.deleteRepo('${esc(r.id)}')" title="Verwijderen">
            <span class="mdi mdi-delete-outline"></span>
          </button>
        </div>`).join('')
      : `<div class="info-box">
          <span class="mdi mdi-information-outline"></span>
          Nog geen repositories. Voeg er een toe via de knop rechtsboven.
        </div>`;

    const stackGrid = _stacks.length
      ? `<div class="stack-grid" id="app-stack-grid">${_stacks.map(_stackCard).join('')}</div>`
      : `<div class="empty"><span class="mdi mdi-store-outline empty-icon"></span>
          <p class="empty-text">Geen stacks gevonden in de repositories</p></div>`;

    return `
      <div style="margin-bottom:16px">${repoList}</div>
      ${repoFilter}
      ${stackGrid}
      <div id="stack-detail-panel"></div>`;
  }

  function _stackCard(s) {
    const logo = s.logo_url
      ? `<img src="${esc(s.logo_url)}" alt="${esc(s.name)}" onerror="this.parentElement.innerHTML=_letterAvatar('${esc(s.name)}')">`
      : _letterAvatar(s.name);

    return `
      <div class="stack-card ${s.installed ? 'installed' : ''}"
           onclick="AppStore.openDetail('${esc(s.repo_id)}','${esc(s.path)}','${esc(s.name)}')">
        <div class="stack-logo-wrap">${logo}</div>
        <div class="stack-head">
          <span class="stack-name">${esc(s.name)}</span>
          ${s.installed
            ? '<span class="status-badge s-running">Geïnstalleerd</span>'
            : ''}
        </div>
        <div class="stack-body">
          ${s.description ? `<div class="stack-desc">${esc(s.description)}</div>` : ''}
          <div class="card-chips">
            ${(s.services || []).map(sv => `<span class="chip">${esc(sv)}</span>`).join('')}
          </div>
        </div>
      </div>`;
  }

  function _letterAvatar(name) {
    const colors = ['#2dd4bf','#60a5fa','#a78bfa','#f472b6','#fb923c','#4ade80'];
    const color  = colors[name.charCodeAt(0) % colors.length];
    const letter = (name || '?')[0].toUpperCase();
    return `<div class="stack-letter-avatar" style="background:${color}">${letter}</div>`;
  }

  function _bindEvents() {
    document.getElementById('app-search')?.addEventListener('input', e => {
      clearTimeout(_searchTimer);
      _searchTimer = setTimeout(() => _filterStacks(e.target.value), 250);
    });
    document.getElementById('app-repo-filter')?.addEventListener('change', e => {
      _filterStacks(document.getElementById('app-search')?.value || '', e.target.value);
    });
    document.getElementById('btn-pull-all-apps')?.addEventListener('click', pullAll);
  }

  function _filterStacks(q, repoId = '') {
    const ql = q.toLowerCase();
    const filtered = _stacks.filter(s => {
      const matchQ = !ql || s.name.toLowerCase().includes(ql) ||
        (s.description || '').toLowerCase().includes(ql);
      const matchR = !repoId || s.repo_id === repoId;
      return matchQ && matchR;
    });
    const grid = document.getElementById('app-stack-grid');
    if (grid) grid.innerHTML = filtered.map(_stackCard).join('') ||
      `<div class="empty"><span class="mdi mdi-magnify"></span><p class="empty-text">Geen resultaten</p></div>`;
  }

  /* ── Detail panel ────────────────────────────────────────────────────────── */
  async function openDetail(repoId, path, name) {
    const panel = document.getElementById('stack-detail-panel');
    if (!panel) return;

    panel.innerHTML = `<div style="text-align:center;padding:20px"><span class="mdi mdi-loading mdi-spin" style="font-size:24px"></span></div>`;
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    const r = await fetch(`/api/git/stacks?repo_id=${encodeURIComponent(repoId)}`)
      .then(r => r.json()).catch(() => ({}));
    const stack = (r.stacks || []).find(s => s.path === path) || { name };

    panel.innerHTML = `
      <div class="acc-panel" style="margin-top:16px">
        <div class="acc-head open" onclick="toggleAcc(this)">
          <span class="mdi mdi-information-outline"></span>
          <span class="acc-title">${esc(stack.name)}</span>
          <button class="btn btn-sm btn-ghost" style="margin-left:auto;margin-right:8px"
            onclick="event.stopPropagation();AppStore.closeDetail()">
            <span class="mdi mdi-close"></span>
          </button>
          <span class="mdi mdi-chevron-right acc-caret"></span>
        </div>
        <div class="acc-body" style="display:block"><div class="acc-content">
          ${stack.description ? `<p style="color:var(--text2);font-size:13px;margin-bottom:14px">${esc(stack.description)}</p>` : ''}
          <div class="field">
            <label>Projectnaam</label>
            <input id="sd-project-name" type="text" value="${esc(stack.name)}" placeholder="Naam voor dit project">
          </div>
          ${stack.readme ? `
            <div style="margin-bottom:14px">
              <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--dim);margin-bottom:6px">README</div>
              <pre style="font-family:var(--mono);font-size:11px;color:var(--text2);background:var(--surface2);padding:10px;border-radius:var(--radius);max-height:140px;overflow-y:auto;white-space:pre-wrap">${esc(stack.readme)}</pre>
            </div>` : ''}
          <div class="modal-actions" style="margin-top:0;padding-top:12px">
            <button class="btn btn-primary" onclick="AppStore.install('${esc(repoId)}','${esc(path)}')">
              <span class="mdi mdi-download"></span> Installeren
            </button>
            <button class="btn" onclick="AppStore.closeDetail()">Annuleren</button>
          </div>
        </div></div>
      </div>`;
  }

  function closeDetail() {
    const panel = document.getElementById('stack-detail-panel');
    if (panel) panel.innerHTML = '';
  }

  /* ── Acties ─────────────────────────────────────────────────────────────── */
  async function install(repoId, path) {
    const name = document.getElementById('sd-project-name')?.value.trim();
    if (!name) { toast('Vul een projectnaam in', 'warn'); return; }
    const d = await apiPost('/api/git/install', { repo_id: repoId, path, name });
    if (d.job_id) {
      pollJob(d.job_id);
      closeDetail();
      showPage('projects');
    } else {
      toast(d.error || 'Installatie mislukt', 'error');
    }
  }

  async function pull(repoId) {
    const d = await apiPost(`/api/repos/${encodeURIComponent(repoId)}/pull`);
    if (d.job_id) pollJob(d.job_id);
    setTimeout(load, 3000);
  }

  async function pullAll() {
    const d = await apiPost('/api/repos/pull-all');
    if (d.job_id) pollJob(d.job_id);
    setTimeout(load, 4000);
  }

  async function deleteRepo(repoId) {
    const repo = _repos.find(r => r.id === repoId);
    const name = repo?.name || repoId;
    if (!confirm(`Repository "${name}" verwijderen?\n\nDe lokale git-cache wordt ook verwijderd.`)) return;
    await fetch(`/api/repos/${encodeURIComponent(repoId)}`, { method: 'DELETE' });
    load();
  }

  /* ── Init ────────────────────────────────────────────────────────────────── */
  function init() {
    document.addEventListener('dm:page', e => {
      if (e.detail === 'app-store') load();
    });
  }

  return { init, load, openDetail, closeDetail, install, pull, pullAll, deleteRepo };
})();

// Hook in to showPage
// dm:page wordt al afgehandeld door AppStore.init() via dm:ready
document.addEventListener('dm:ready', () => AppStore.init());
