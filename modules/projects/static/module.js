/* ═══════════════════════════════════════════════════════════════════════════
   module_projects.js — Extra projectfuncties: env/compose editor, logs, remove
   ═══════════════════════════════════════════════════════════════════════════ */
'use strict';

// Extra CSS voor editors en remove modal
(function() {
  const s = document.createElement('style');
  s.textContent = `
.code-editor{font-family:var(--mono);font-size:12px;min-height:280px;resize:vertical;line-height:1.7;tab-size:2}
`;
  document.head.appendChild(s);
})();

// Extra modals injecteren in body
(function() {
  const modals = document.createElement('div');
  modals.innerHTML = `
  <!-- Env editor -->
  <div class="overlay" id="m-env">
    <div class="modal">
      <div class="modal-title"><span class="mdi mdi-file-cog-outline"></span> <span id="m-env-title">.env</span></div>
      <div class="field"><textarea class="code-editor" id="env-ed" spellcheck="false"></textarea></div>
      <div class="modal-actions">
        <button class="btn" onclick="closeModal('m-env')">Annuleren</button>
        <button class="btn btn-primary" onclick="saveEnv()">
          <span class="mdi mdi-content-save"></span> Opslaan
        </button>
      </div>
    </div>
  </div>

  <!-- Compose editor -->
  <div class="overlay" id="m-compose">
    <div class="modal" style="width:min(800px,95vw)">
      <div class="modal-title"><span class="mdi mdi-file-code-outline"></span> <span id="m-compose-title">docker-compose.yaml</span></div>
      <div class="field"><textarea class="code-editor" id="compose-ed" spellcheck="false"></textarea></div>
      <div class="modal-actions">
        <button class="btn" onclick="closeModal('m-compose')">Annuleren</button>
        <button class="btn btn-primary" onclick="saveCompose()">
          <span class="mdi mdi-content-save"></span> Opslaan
        </button>
      </div>
    </div>
  </div>

  <!-- Remove modal -->
  <div class="overlay" id="m-remove">
    <div class="modal" style="max-width:420px">
      <div class="modal-title" style="color:var(--danger)">
        <span class="mdi mdi-delete-alert-outline"></span> Verwijderen
      </div>
      <p style="font-size:13px;color:var(--text2);margin-bottom:18px">
        Wat wil je verwijderen van <strong id="rm-name" style="color:var(--white)"></strong>?
      </p>
      <div style="display:flex;flex-direction:column;gap:8px">
        <button class="btn" onclick="doRemove('stack')">
          <span class="mdi mdi-stop-circle-outline"></span> Alleen stack stoppen (down)
        </button>
        <button class="btn" onclick="doRemove('full')">
          <span class="mdi mdi-delete-outline"></span> Stack + volumes + projectmap
        </button>
        <button class="btn btn-danger" onclick="doRemove('all')">
          <span class="mdi mdi-nuke"></span> Alles inclusief datamap
        </button>
      </div>
      <div class="modal-actions">
        <button class="btn" onclick="closeModal('m-remove')">Annuleren</button>
      </div>
    </div>
  </div>`;
  document.body.appendChild(modals);

  // Overlay click-to-close
  modals.querySelectorAll('.overlay').forEach(o =>
    o.addEventListener('click', e => { if (e.target === o) o.classList.remove('open'); })
  );
})();

/* ── State ─────────────────────────────────────────────────────────────────── */
let _currentEnvProject     = null;
let _currentComposeProject = null;
let _currentRemoveProject  = null;

/* ── Env editor ─────────────────────────────────────────────────────────────── */
async function openEnv(name) {
  _currentEnvProject = name;
  document.getElementById('m-env-title').textContent = `.env — ${name}`;
  const r = await fetch(`/api/projects/${encodeURIComponent(name)}/env`).then(r => r.json());
  document.getElementById('env-ed').value = r.content || `# .env voor ${name}\n`;
  openModal('m-env');
}

async function saveEnv() {
  await fetch(`/api/projects/${encodeURIComponent(_currentEnvProject)}/env`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: document.getElementById('env-ed').value }),
  });
  closeModal('m-env');
  toast(`.env opgeslagen voor ${_currentEnvProject}`, 'ok');
}

/* ── Compose editor ──────────────────────────────────────────────────────────── */
async function openCompose(name) {
  _currentComposeProject = name;
  document.getElementById('m-compose-title').textContent = `docker-compose.yaml — ${name}`;
  const r = await fetch(`/api/projects/${encodeURIComponent(name)}/compose`).then(r => r.json());
  document.getElementById('compose-ed').value = r.content || '';
  openModal('m-compose');
}

async function saveCompose() {
  await fetch(`/api/projects/${encodeURIComponent(_currentComposeProject)}/compose`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: document.getElementById('compose-ed').value }),
  });
  closeModal('m-compose');
  toast(`Compose opgeslagen voor ${_currentComposeProject}`, 'ok');
}

/* ── Logs ────────────────────────────────────────────────────────────────────── */
async function viewLogs(name) {
  const d = await fetch(`/api/projects/${encodeURIComponent(name)}/logs?tail=300`).then(r => r.json());
  if (d.job_id) pollJob(d.job_id);
}

/* ── Remove ─────────────────────────────────────────────────────────────────── */
function openRemove(name) {
  _currentRemoveProject = name;
  document.getElementById('rm-name').textContent = name;
  openModal('m-remove');
}

async function doRemove(mode) {
  closeModal('m-remove');
  const d = await apiPost(`/api/projects/${encodeURIComponent(_currentRemoveProject)}/remove`, { mode });
  if (d.job_id) {
    pollJob(d.job_id);
    setTimeout(loadProjects, 4000);
  }
}

/* ── Uitgebreide kaart render (vervangt de basisversie) ──────────────────────── */
// Override renderProjectCard met volledige acties
window.renderProjectCard = function(p) {
  const running = p.running, nc = p.no_compose;
  const icon = nc ? 'mdi-alert-outline' : running ? 'mdi-play-circle' : 'mdi-stop-circle-outline';
  const icls = nc ? 'status-warn' : running ? 'status-ok' : 'status-dim';
  const chips = (p.containers || []).map(c =>
    `<span class="chip ${c.running ? 'up' : ''}">${esc(c.name)}</span>`).join('');
  const ports = (p.containers || [])
    .flatMap(c => (c.ports || '').split(',').filter(Boolean))
    .slice(0, 4).join('  ');

  const baseActions = !nc ? `
    <button class="btn btn-sm ${running ? 'btn-danger' : ''}"
      onclick="projectAction('${esc(p.name)}','${running ? 'stop' : 'start'}')">
      <span class="mdi ${running ? 'mdi-stop' : 'mdi-play'}"></span> ${running ? 'Stop' : 'Start'}
    </button>
    <button class="btn btn-sm" onclick="projectAction('${esc(p.name)}','restart')">
      <span class="mdi mdi-restart"></span>
    </button>
    <button class="btn btn-sm" onclick="projectAction('${esc(p.name)}','update')">
      <span class="mdi mdi-update"></span>
    </button>` : '';

  const extraActions = `
    <button class="btn btn-sm btn-ghost" onclick="openEnv('${esc(p.name)}')" title=".env bewerken">
      <span class="mdi mdi-file-cog-outline"></span>
    </button>
    <button class="btn btn-sm btn-ghost" onclick="openCompose('${esc(p.name)}')" title="Compose bewerken">
      <span class="mdi mdi-file-code-outline"></span>
    </button>
    <button class="btn btn-sm btn-ghost" onclick="viewLogs('${esc(p.name)}')" title="Logs bekijken">
      <span class="mdi mdi-text-box-outline"></span>
    </button>
    <button class="btn btn-sm btn-ghost" onclick="projectAction('${esc(p.name)}','backup')" title="Backup">
      <span class="mdi mdi-archive-arrow-down-outline"></span>
    </button>
    <button class="btn btn-sm btn-ghost btn-danger" onclick="openRemove('${esc(p.name)}')" title="Verwijderen" style="margin-left:auto">
      <span class="mdi mdi-delete-outline"></span>
    </button>`;

  return `
    <div class="project-card ${running ? 'running' : nc ? 'no-compose' : 'stopped'}">
      <div class="card-head">
        <span class="mdi ${icon} card-status-icon ${icls}"></span>
        <span class="card-name">${esc(p.name)}</span>
        <span class="status-badge ${running ? 's-running' : nc ? 's-missing' : 's-stopped'}">
          ${running ? 'Running' : nc ? 'No compose' : 'Stopped'}
        </span>
      </div>
      <div class="card-body">
        ${chips ? `<div class="card-chips">${chips}</div>` : ''}
        ${ports ? `<div class="ports-line"><span class="mdi mdi-connection"></span> ${esc(ports)}</div>` : ''}
        <div class="card-actions">
          ${baseActions}${extraActions}
        </div>
      </div>
    </div>`;
};
