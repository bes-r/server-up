"""
MQTT module — verbind met een MQTT broker, bekijk topics en publiceer berichten.
Vereist: pip install paho-mqtt
"""
from flask import Blueprint, jsonify, request
from modules.base import ModuleBase
from core import config, audit


class MqttModule(ModuleBase):
    MODULE_ID   = "mqtt"
    MODULE_NAME = "MQTT"
    MODULE_ICON = "📡"
    MODULE_DESC = "Monitor en beheer een MQTT broker"
    VERSION     = "1.0.1"

    def pages(self):
        return [
            {"id": "mqtt", "label": "MQTT", "icon": "📡",
             "group": "main", "default": True, "dashboard_widget": True},
        ]

    def blueprint(self) -> Blueprint:
        bp = Blueprint("mqtt", __name__)

        @bp.route("/api/mqtt/status")
        def mqtt_status():
            cfg = config.get()
            if not cfg.get("MQTT_HOST"):
                return jsonify(connected=False, reason="Geen MQTT host ingesteld")
            ok, msg = _test_connection(cfg)
            return jsonify(connected=ok, reason=msg,
                           host=cfg["MQTT_HOST"], port=cfg["MQTT_PORT"])

        @bp.route("/api/mqtt/publish", methods=["POST"])
        def mqtt_publish():
            cfg  = config.get()
            data = request.json or {}
            topic   = data.get("topic", "").strip()
            payload = data.get("payload", "").strip()
            if not topic:
                return jsonify(error="Topic verplicht"), 400
            ok, msg = _publish(cfg, topic, payload)
            status = "ok" if ok else "error"
            audit.log("mqtt", "publish", status,
                      details={"topic": topic}, remote_ip=request.remote_addr)
            return jsonify(ok=ok, msg=msg)

        @bp.route("/api/mqtt/test-ha", methods=["POST"])
        def test_ha():
            """Stuur een test melding naar Home Assistant via MQTT."""
            cfg = config.get()
            topic = f"{cfg.get('MQTT_TOPIC_BASE','server/alerts')}/test"
            ok, msg = _publish(cfg, topic, "Server Up test melding")
            return jsonify(ok=ok, msg=msg)

        return bp


# ── Helpers ────────────────────────────────────────────────────────────────────

def _test_connection(cfg: dict) -> tuple[bool, str]:
    try:
        import paho.mqtt.client as mqtt
        client = mqtt.Client()
        if cfg.get("MQTT_USER"):
            client.username_pw_set(cfg["MQTT_USER"], cfg.get("MQTT_PASS", ""))
        result = {}
        def on_connect(c, ud, flags, rc):
            result["rc"] = rc
        client.on_connect = on_connect
        client.connect(cfg["MQTT_HOST"], int(cfg.get("MQTT_PORT", 1883)), keepalive=5)
        client.loop_start()
        import time; time.sleep(1.5)
        client.loop_stop(); client.disconnect()
        if result.get("rc") == 0:
            return True, "Verbonden"
        return False, f"Verbinding geweigerd (rc={result.get('rc')})"
    except ImportError:
        return False, "paho-mqtt niet geïnstalleerd (pip install paho-mqtt)"
    except Exception as e:
        return False, str(e)


def _publish(cfg: dict, topic: str, payload: str) -> tuple[bool, str]:
    try:
        import paho.mqtt.publish as publish
        auth = None
        if cfg.get("MQTT_USER"):
            auth = {"username": cfg["MQTT_USER"], "password": cfg.get("MQTT_PASS", "")}
        publish.single(
            topic, payload,
            hostname=cfg["MQTT_HOST"],
            port=int(cfg.get("MQTT_PORT", 1883)),
            auth=auth,
        )
        return True, f"Gepubliceerd naar {topic}"
    except ImportError:
        return False, "paho-mqtt niet geïnstalleerd"
    except Exception as e:
        return False, str(e)
