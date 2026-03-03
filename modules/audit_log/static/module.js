/* ═══════════════════════════════════════════════════════════════════════════
   module_audit_log.js — Audit log weergave
   ═══════════════════════════════════════════════════════════════════════════ */
'use strict';

const AuditLog = (() => {
  const LIMIT = 50;
  let _offset = 0;

  async function load() {
    const sec = document.getElementById('sec-audit_log');
    if (!sec) return;

    // Build HTML als het nog leeg is
    if (!document.getElementById('audit-body')) {
      const content = document.getElementById('mod-content-audit_log');
      if (content) content.innerHTML = _buildHTML();
      _bindEvents();
    }

    await _fetchPage();
  }

  function _buildHTML() {
    return `
      <div class="audit-filters">
        <div class="search-wrap" style="max-width:280px">
          <span class="mdi mdi-magnify"></span>
          <input type="text" class="search-input" id="af-search" placeholder="Zoek…" oninput="AuditLog.reload()">
        </div>
        <select class="audit-filter" id="af-module" onchange="AuditLog.reload()">
          <option value="">Alle modules</option>
        </select>
        <select class="audit-filter" id="af-status" onchange="AuditLog.reload()">
          <option value="">Alle statussen</option>
          <option value="ok">✔ OK</option>
          <option value="error">✖ Fout</option>
          <option value="warn">⚠ Waarschuwing</option>
        </select>
        <span id="audit-count" style="font-size:11px;color:var(--dim);margin-left:4px"></span>
        <button class="btn btn-sm btn-ghost btn-danger" style="margin-left:auto" onclick="AuditLog.clear()">
          <span class="mdi mdi-delete-outline"></span> Wissen
        </button>
      </div>
      <div class="audit-wrap">
        <table class="audit-table">
          <thead>
            <tr>
              <th>Tijd</th>
              <th>Module</th>
              <th>Actie</th>
              <th>Project</th>
              <th>Status</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody id="audit-body">
            <tr><td colspan="6" style="text-align:center;padding:20px">
              <span class="mdi mdi-loading mdi-spin"></span>
            </td></tr>
          </tbody>
        </table>
        <div class="audit-pagination">
          <button class="btn btn-sm" id="audit-prev" onclick="AuditLog.prev()" disabled>
            <span class="mdi mdi-chevron-left"></span> Vorige
          </button>
          <span id="audit-page-info" style="font-size:11px;color:var(--text2);flex:1;text-align:center"></span>
          <button class="btn btn-sm" id="audit-next" onclick="AuditLog.next()" disabled>
            Volgende <span class="mdi mdi-chevron-right"></span>
          </button>
        </div>
      </div>`;
  }

  function _bindEvents() {
    // Module filter vullen
    fetch('/api/audit/modules').then(r => r.json()).then(r => {
      const sel = document.getElementById('af-module');
      if (!sel) return;
      sel.innerHTML = '<option value="">Alle modules</option>' +
        (r.modules || []).map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('');
    }).catch(() => {});
  }

  async function _fetchPage() {
    const q      = document.getElementById('af-search')?.value || '';
    const module = document.getElementById('af-module')?.value || '';
    const status = document.getElementById('af-status')?.value || '';
    const url = `/api/audit?limit=${LIMIT}&offset=${_offset}&q=${encodeURIComponent(q)}&module=${encodeURIComponent(module)}&status=${encodeURIComponent(status)}`;

    const r = await fetch(url).then(r => r.json()).catch(() => ({ entries: [], total: 0 }));

    const body = document.getElementById('audit-body');
    if (!body) return;

    const rows = (r.entries || []);
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--dim);padding:20px">Geen entries gevonden</td></tr>`;
    } else {
      body.innerHTML = rows.map(e => `
        <tr>
          <td class="audit-ts">${(e.ts || '').replace('T', ' ').replace('Z', '')}</td>
          <td class="audit-module">${esc(e.module)}</td>
          <td class="audit-action">${esc(e.action)}</td>
          <td class="audit-project">${esc(e.project || '')}</td>
          <td class="${e.status === 'ok' ? 'audit-ok' : 'audit-error'}">
            <span class="mdi ${e.status === 'ok' ? 'mdi-check-circle-outline' : 'mdi-close-circle-outline'}"></span>
            ${esc(e.status)}
          </td>
          <td class="audit-dim" style="color:var(--text2);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
              title="${esc(e.details || '')}">${esc(e.details || '')}</td>
        </tr>`).join('');
    }

    const total = r.total || 0;
    const el = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    el('audit-count', `${total} entries`);
    el('audit-page-info', `${_offset + 1}–${Math.min(_offset + LIMIT, total)} van ${total}`);
    const prev = document.getElementById('audit-prev');
    const next = document.getElementById('audit-next');
    if (prev) prev.disabled = _offset === 0;
    if (next) next.disabled = _offset + LIMIT >= total;
  }

  function reload() { _offset = 0; _fetchPage(); }
  function prev()   { _offset = Math.max(0, _offset - LIMIT); _fetchPage(); }
  function next()   { _offset += LIMIT; _fetchPage(); }

  async function clear() {
    if (!confirm('Audit log wissen?')) return;
    await apiPost('/api/audit/clear');
    _offset = 0;
    _fetchPage();
    toast('Audit log gewist', 'ok');
  }

  function init() {}

  return { init, load, reload, prev, next, clear };
})();

document.addEventListener('dm:page', e => {
  if (e.detail === 'audit_log') AuditLog.load();
});
