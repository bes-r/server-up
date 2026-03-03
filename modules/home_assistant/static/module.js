'use strict';

/* ═══════════════════════════════════════════════════════════════════════════
   module_home_assistant.js — Home Assistant integratie
   ═══════════════════════════════════════════════════════════════════════════ */

const HA = (() => {
  let _status = null;
  let _refreshTimer = null;

  // ── Render pagina ─────────────────────────────────────────────────────────

  async function load() {
    const el = document.getElementById('home-assistant-content');
    if (!el) return;

    el.innerHTML = `<div class="empty"><span class="mdi mdi-loading mdi-spin"></span>
      <p class="empty-text">Laden…</p></div>`;

    await _refresh(el);
    clearInterval(_refreshTimer);
    _refreshTimer = setInterval(() => _refresh(el), 30000);
  }

  async function _refresh(el) {
    try {
      _status = await fetch('/api/ha/status').then(r => r.json());
    } catch(e) {
      _status = { connected: false, reason: e.message, configured: false };
    }
    el.innerHTML = _renderPage();
    _bindEvents(el);
  }

  function _renderPage() {
    const st = _status || {};
    const connIcon  = st.connected ? 'mdi-home-circle text-ok' : 'mdi-home-circle-outline text-warn';
    const connLabel = st.connected
      ? `Verbonden <span class="badge badge-ok">HA ${esc(st.version || '?')}</span>`
      : `Niet verbonden${st.reason ? ` — <span style="color:var(--dim)">${esc(st.reason)}</span>` : ''}`;

    return `
    <div class="section">
      <div class="page-header">
        <div class="page-title"><span class="mdi mdi-home-assistant"></span> Home Assistant</div>
      </div>

      <!-- Status balk -->
      <div class="acc-panel" style="margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:12px;padding:12px 16px">
          <span class="mdi ${connIcon}" style="font-size:24px"></span>
          <div>
            <div style="font-weight:600">${connLabel}</div>
            ${st.configured && !st.connected ? `
              <div style="font-size:11px;color:var(--dim);margin-top:2px">
                Controleer de URL en het token in Instellingen
              </div>` : ''}
          </div>
          <button class="btn btn-sm" style="margin-left:auto" onclick="HA.testConnection()">
            <span class="mdi mdi-connection"></span> Testen
          </button>
        </div>
      </div>

      ${!st.configured ? _renderNotConfigured() : (st.connected ? _renderConnected() : _renderOffline())}
    </div>`;
  }

  function _renderNotConfigured() {
    return `
    <div class="empty">
      <span class="mdi mdi-home-remove-outline" style="font-size:48px;color:var(--dim)"></span>
      <p class="empty-text">Home Assistant is nog niet geconfigureerd</p>
      <p style="color:var(--dim);font-size:13px;max-width:400px;text-align:center">
        Stel de URL en een Long-Lived Access Token in via
        <strong>Instellingen → Home Assistant</strong>.
      </p>
      <button class="btn" onclick="showPage('settings')" style="margin-top:12px">
        <span class="mdi mdi-cog-outline"></span> Naar instellingen
      </button>
    </div>`;
  }

  function _renderOffline() {
    return `
    <div class="empty">
      <span class="mdi mdi-home-off-outline" style="font-size:48px;color:var(--warn)"></span>
      <p class="empty-text" style="color:var(--warn)">Verbinding mislukt</p>
      <p style="color:var(--dim);font-size:13px">${esc(_status?.reason || '')}</p>
    </div>`;
  }

  function _renderConnected() {
    return `
    <!-- Snelle acties -->
    <div class="acc-panel" style="margin-bottom:16px">
      <div class="acc-header" onclick="this.parentElement.classList.toggle('open')">
        <span class="mdi mdi-lightning-bolt-outline"></span> Snelle acties
        <span class="acc-arrow mdi mdi-chevron-down"></span>
      </div>
      <div class="acc-body">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px">

          <!-- Service aanroepen -->
          <div class="field">
            <label>Domein</label>
            <input id="ha-svc-domain" placeholder="light" value="homeassistant">
          </div>
          <div class="field">
            <label>Service</label>
            <input id="ha-svc-service" placeholder="turn_on" value="check_config">
          </div>
          <div class="field" style="grid-column:1/-1">
            <label>Data (JSON, optioneel)</label>
            <input id="ha-svc-data" placeholder='{"entity_id":"light.woonkamer"}'>
          </div>
          <div style="grid-column:1/-1">
            <button class="btn btn-sm" onclick="HA.callService()">
              <span class="mdi mdi-play-circle-outline"></span> Service uitvoeren
            </button>
            <span id="ha-svc-result" style="font-size:12px;color:var(--text2);margin-left:8px"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Notificatie -->
    <div class="acc-panel" style="margin-bottom:16px">
      <div class="acc-header" onclick="this.parentElement.classList.toggle('open')">
        <span class="mdi mdi-bell-outline"></span> Notificatie sturen
        <span class="acc-arrow mdi mdi-chevron-down"></span>
      </div>
      <div class="acc-body">
        <div style="padding:12px;display:flex;flex-direction:column;gap:8px">
          <div class="field">
            <label>Bericht</label>
            <input id="ha-notify-msg" placeholder="Testbericht van Server Up" value="Test van Server Up">
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
            <div class="field">
              <label>Titel</label>
              <input id="ha-notify-title" placeholder="Server Up" value="Server Up">
            </div>
            <div class="field">
              <label>Service target</label>
              <input id="ha-notify-target" placeholder="notify of notify.mobile_app_..." value="notify">
            </div>
          </div>
          <div>
            <button class="btn btn-sm" onclick="HA.sendNotification()">
              <span class="mdi mdi-send-outline"></span> Versturen
            </button>
            <span id="ha-notify-result" style="font-size:12px;color:var(--text2);margin-left:8px"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Webhook -->
    <div class="acc-panel">
      <div class="acc-header" onclick="this.parentElement.classList.toggle('open')">
        <span class="mdi mdi-webhook"></span> Webhook
        <span class="acc-arrow mdi mdi-chevron-down"></span>
      </div>
      <div class="acc-body">
        <div style="padding:12px;display:flex;flex-direction:column;gap:8px">
          <div class="field">
            <label>Webhook ID</label>
            <input id="ha-webhook-id" placeholder="server_up_event">
          </div>
          <div>
            <button class="btn btn-sm" onclick="HA.triggerWebhook()">
              <span class="mdi mdi-webhook"></span> Trigger
            </button>
            <span id="ha-webhook-result" style="font-size:12px;color:var(--text2);margin-left:8px"></span>
          </div>
        </div>
      </div>
    </div>`;
  }

  function _bindEvents(el) {
    // Accordion open eerste panel als verbonden
    if (_status?.connected) {
      el.querySelector('.acc-panel')?.classList.add('open');
    }
  }

  // ── API acties ────────────────────────────────────────────────────────────

  async function testConnection() {
    const btn = document.querySelector('.btn[onclick="HA.testConnection()"]');
    if (btn) btn.disabled = true;
    try {
      const r = await fetch('/api/ha/status').then(r => r.json());
      _status = r;
      const el = document.getElementById('home-assistant-content');
      if (el) { el.innerHTML = _renderPage(); _bindEvents(el); }
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function callService() {
    const domain  = document.getElementById('ha-svc-domain')?.value.trim();
    const service = document.getElementById('ha-svc-service')?.value.trim();
    const dataRaw = document.getElementById('ha-svc-data')?.value.trim();
    const result  = document.getElementById('ha-svc-result');
    let svcData = {};
    if (dataRaw) {
      try { svcData = JSON.parse(dataRaw); }
      catch { if (result) result.textContent = '✖ Ongeldige JSON'; return; }
    }
    if (result) result.textContent = 'Bezig…';
    const r = await apiPost('/api/ha/service', { domain, service, data: svcData });
    if (result) {
      result.textContent = r.ok ? '✔ Uitgevoerd' : `✖ ${r.msg||'Fout'}`;
      result.style.color = r.ok ? 'var(--ok)' : 'var(--danger)';
    }
  }

  async function sendNotification() {
    const msg    = document.getElementById('ha-notify-msg')?.value.trim();
    const title  = document.getElementById('ha-notify-title')?.value.trim();
    const target = document.getElementById('ha-notify-target')?.value.trim();
    const result = document.getElementById('ha-notify-result');
    if (result) result.textContent = 'Bezig…';
    const r = await apiPost('/api/ha/notify', { message: msg, title, target });
    if (result) {
      result.textContent = r.ok ? '✔ Verzonden' : `✖ ${r.msg||'Fout'}`;
      result.style.color = r.ok ? 'var(--ok)' : 'var(--danger)';
    }
  }

  async function triggerWebhook() {
    const id     = document.getElementById('ha-webhook-id')?.value.trim();
    const result = document.getElementById('ha-webhook-result');
    if (!id) { if (result) result.textContent = 'Vul een webhook ID in'; return; }
    if (result) result.textContent = 'Bezig…';
    const r = await apiPost('/api/ha/webhook', { webhook_id: id });
    if (result) {
      result.textContent = r.ok ? '✔ Getriggerd' : `✖ ${r.msg||'Fout'}`;
      result.style.color = r.ok ? 'var(--ok)' : 'var(--danger)';
    }
  }

  return { load, testConnection, callService, sendNotification, triggerWebhook };
})();

// Auto-load
document.addEventListener('dm:page', e => { if (e.detail === 'home-assistant') HA.load(); });
