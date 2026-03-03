/* ═══════════════════════════════════════════════════════════════════════════
   module_mqtt.js — MQTT status en publish
   ═══════════════════════════════════════════════════════════════════════════ */
'use strict';

const MqttModule = (() => {

  function load() {
    const content = document.getElementById('mod-content-mqtt');
    if (!content || content.dataset.built) return;
    content.dataset.built = '1';
    content.innerHTML = `
      <div class="stat-row" style="margin-bottom:20px">
        <div class="stat-card">
          <div class="stat-icon" id="mqtt-dot-wrap" style="background:var(--surface2)">
            <span class="mdi mdi-broadcast" style="color:var(--dim)"></span>
          </div>
          <div>
            <div class="stat-val" id="mqtt-status-val" style="font-size:14px">–</div>
            <div class="stat-label" id="mqtt-status-sub">Onbekend</div>
          </div>
        </div>
      </div>

      <div class="acc-panel">
        <div class="acc-head open" onclick="toggleAcc(this)">
          <span class="mdi mdi-send-outline"></span>
          <span class="acc-title">Bericht publiceren</span>
          <span class="mdi mdi-chevron-right acc-caret"></span>
        </div>
        <div class="acc-body" style="display:block"><div class="acc-content">
          <div class="settings-grid">
            <div class="field">
              <label>Topic</label>
              <input id="mqtt-topic" type="text" placeholder="server/alerts/test">
            </div>
            <div class="field">
              <label>Payload</label>
              <input id="mqtt-payload" type="text" placeholder='{"message":"test"}'>
            </div>
          </div>
          <div style="display:flex;gap:8px;margin-top:4px">
            <button class="btn btn-primary" onclick="MqttModule.publish()">
              <span class="mdi mdi-send"></span> Publiceren
            </button>
            <button class="btn" onclick="MqttModule.testHa()">
              <span class="mdi mdi-home-assistant"></span> Test HA Webhook
            </button>
          </div>
        </div></div>
      </div>`;

    checkStatus();
  }

  async function checkStatus() {
    const r = await fetch('/api/mqtt/status').then(r => r.json()).catch(() => ({}));
    const val = document.getElementById('mqtt-status-val');
    const sub = document.getElementById('mqtt-status-sub');
    const dot = document.getElementById('mqtt-dot-wrap');
    if (val) {
      val.textContent = r.connected ? 'Verbonden' : 'Niet verbonden';
      val.style.color = r.connected ? 'var(--ok)' : 'var(--danger)';
    }
    if (sub) sub.textContent = (r.reason || '') + (r.host ? ` — ${r.host}:${r.port}` : '');
    if (dot) dot.style.background = r.connected ? 'var(--ok-dim)' : 'var(--danger-dim)';
  }

  async function publish() {
    const topic   = document.getElementById('mqtt-topic')?.value.trim();
    const payload = document.getElementById('mqtt-payload')?.value.trim();
    if (!topic) { toast('Topic is verplicht', 'warn'); return; }
    const r = await apiPost('/api/mqtt/publish', { topic, payload });
    toast(r.msg || (r.ok ? 'Gepubliceerd' : 'Fout'), r.ok ? 'ok' : 'error');
  }

  async function testHa() {
    const r = await apiPost('/api/mqtt/test-ha');
    toast(r.msg || (r.ok ? 'Webhook verstuurd' : 'Fout'), r.ok ? 'ok' : 'error');
  }

  return { load, checkStatus, publish, testHa };
})();

document.addEventListener('dm:page', e => {
  if (e.detail === 'mqtt') MqttModule.load();
});
