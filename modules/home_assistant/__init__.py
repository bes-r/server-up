"""
Home Assistant module — koppel Server Up met Home Assistant.

Ondersteunt twee methodes:
  1. REST API  — via HA Long-Lived Access Token
  2. MQTT      — via de MQTT module (optioneel)

Functies:
  - Verbindingsstatus controleren
  - Entiteiten opvragen
  - Services aanroepen (bijv. licht aan/uit, script uitvoeren)
  - Webhook triggeren in HA
  - Notificatie sturen via HA notify service
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from modules.base import ModuleBase
from core import config, audit


class HomeAssistantModule(ModuleBase):
    MODULE_ID   = "home_assistant"
    MODULE_NAME = "Home Assistant"
    MODULE_ICON = "🏠"
    MODULE_DESC = "Koppel Server Up met Home Assistant via REST API of MQTT"
    VERSION     = "1.0.0"

    def pages(self):
        return [
            {
                "id":               "home-assistant",
                "label":            "Home Assistant",
                "icon":             "🏠",
                "group":            "connections",
                "default":          True,
                "dashboard_widget": True,
            }
        ]

    def settings_schema(self):
        """Velden die in de instellingen-UI verschijnen."""
        return [
            {"key": "HA_URL",   "label": "Home Assistant URL",
             "placeholder": "http://homeassistant.local:8123", "type": "text"},
            {"key": "HA_TOKEN", "label": "Long-Lived Access Token",
             "placeholder": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "type": "password"},
            {"key": "HA_WEBHOOK_ID", "label": "Webhook ID (optioneel)",
             "placeholder": "server_up_events", "type": "text"},
        ]

    def blueprint(self) -> Blueprint:
        bp = Blueprint("home_assistant", __name__)

        # ── Status ────────────────────────────────────────────────────────────

        @bp.route("/api/ha/status")
        def ha_status():
            cfg = config.get()
            url = cfg.get("HA_URL", "").rstrip("/")
            if not url:
                return jsonify(connected=False, reason="Geen HA URL ingesteld",
                               configured=False)
            ok, data = _api_get(cfg, "/api/")
            if ok:
                return jsonify(connected=True, version=data.get("version", "?"),
                               message=data.get("message", ""), configured=True)
            return jsonify(connected=False, reason=data, configured=True)

        # ── Entiteiten ────────────────────────────────────────────────────────

        @bp.route("/api/ha/states")
        def ha_states():
            """Geeft alle HA entiteiten terug, optioneel gefilterd op domein."""
            cfg    = config.get()
            domain = request.args.get("domain", "")
            ok, data = _api_get(cfg, "/api/states")
            if not ok:
                return jsonify(ok=False, msg=data), 503
            if domain:
                data = [e for e in data if e.get("entity_id", "").startswith(domain + ".")]
            # Stuur alleen de relevante velden mee
            result = [
                {
                    "entity_id":    e["entity_id"],
                    "state":        e.get("state", ""),
                    "friendly_name": e.get("attributes", {}).get("friendly_name", ""),
                    "domain":       e["entity_id"].split(".")[0],
                }
                for e in (data if isinstance(data, list) else [])
            ]
            return jsonify(states=result)

        @bp.route("/api/ha/state/<path:entity_id>")
        def ha_state(entity_id):
            cfg = config.get()
            ok, data = _api_get(cfg, f"/api/states/{entity_id}")
            if not ok:
                return jsonify(ok=False, msg=data), 404
            return jsonify(data)

        # ── Services ──────────────────────────────────────────────────────────

        @bp.route("/api/ha/service", methods=["POST"])
        def ha_call_service():
            """
            Roep een HA service aan.
            Body: { "domain": "light", "service": "turn_on",
                    "data": { "entity_id": "light.woonkamer" } }
            """
            cfg  = config.get()
            body = request.json or {}
            domain  = body.get("domain", "").strip()
            service = body.get("service", "").strip()
            svc_data = body.get("data", {})
            if not domain or not service:
                return jsonify(ok=False, msg="domain en service zijn verplicht"), 400
            ok, resp = _api_post(cfg, f"/api/services/{domain}/{service}", svc_data)
            if ok:
                audit.log("home_assistant", "call_service", "ok",
                          details={"domain": domain, "service": service})
            return jsonify(ok=ok, msg=resp if isinstance(resp, str) else "OK")

        # ── Webhook ───────────────────────────────────────────────────────────

        @bp.route("/api/ha/webhook", methods=["POST"])
        def ha_webhook():
            """Trigger een HA webhook."""
            cfg        = config.get()
            webhook_id = (request.json or {}).get("webhook_id") or cfg.get("HA_WEBHOOK_ID", "")
            payload    = (request.json or {}).get("payload", {})
            if not webhook_id:
                return jsonify(ok=False, msg="Geen webhook ID opgegeven"), 400
            ok, resp = _api_post(cfg, f"/api/webhook/{webhook_id}", payload)
            audit.log("home_assistant", "webhook", "ok" if ok else "error",
                      details={"id": webhook_id})
            return jsonify(ok=ok, msg=resp if isinstance(resp, str) else "Webhook verzonden")

        # ── Notificaties ──────────────────────────────────────────────────────

        @bp.route("/api/ha/notify", methods=["POST"])
        def ha_notify():
            """Stuur een notificatie via HA."""
            cfg     = config.get()
            body    = request.json or {}
            message = body.get("message", "Bericht van Server Up")
            title   = body.get("title", "Server Up")
            target  = body.get("target", "notify")   # bijv. "notify.mobile_app_telefoon"
            if "." not in target:
                target = f"notify.{target}"
            domain, service = target.split(".", 1)
            ok, resp = _api_post(cfg, f"/api/services/{domain}/{service}",
                                 {"message": message, "title": title})
            return jsonify(ok=ok, msg=resp if isinstance(resp, str) else "Notificatie verzonden")

        return bp


# ── Helpers ────────────────────────────────────────────────────────────────────

def _headers(cfg: dict) -> dict:
    token = cfg.get("HA_TOKEN", "")
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _api_get(cfg: dict, path: str) -> tuple[bool, any]:
    import urllib.request, urllib.error, json as _json
    url = cfg.get("HA_URL", "").rstrip("/") + path
    try:
        req = urllib.request.Request(url, headers=_headers(cfg))
        with urllib.request.urlopen(req, timeout=8) as r:
            return True, _json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)


def _api_post(cfg: dict, path: str, data: dict) -> tuple[bool, any]:
    import urllib.request, urllib.error, json as _json
    url  = cfg.get("HA_URL", "").rstrip("/") + path
    body = _json.dumps(data).encode()
    try:
        req = urllib.request.Request(url, data=body, headers=_headers(cfg), method="POST")
        with urllib.request.urlopen(req, timeout=8) as r:
            text = r.read().decode()
            return True, _json.loads(text) if text.strip() else "OK"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)
