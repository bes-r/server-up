"""Audit Log module — bekijk en doorzoek de audit log."""
from flask import Blueprint, jsonify, request
from modules.base import ModuleBase
from core import audit


class AuditLogModule(ModuleBase):
    MODULE_ID   = "audit_log"
    MODULE_NAME = "Audit Log"
    MODULE_ICON = "📋"
    MODULE_DESC = "Overzicht van alle uitgevoerde acties"
    VERSION     = "1.1.0"

    def pages(self):
        return [
            {"id": "audit_log", "label": "Audit Log", "icon": "📋",
             "group": "system", "default": True, "dashboard_widget": False},
        ]

    def blueprint(self) -> Blueprint:
        bp = Blueprint("audit_log", __name__)

        @bp.route("/api/audit")
        def get_audit():
            limit   = min(int(request.args.get("limit", 100)), 500)
            offset  = int(request.args.get("offset", 0))
            module  = request.args.get("module", "")
            project = request.args.get("project", "")
            status  = request.args.get("status", "")
            search  = request.args.get("q", "")
            entries = audit.query(limit, offset, module, project, search, status)
            total   = audit.count()
            return jsonify(entries=entries, total=total, limit=limit, offset=offset)

        @bp.route("/api/audit/modules")
        def get_modules():
            """Geef lijst van modules die log-entries hebben."""
            from core.audit import _conn
            with _conn() as conn:
                rows = conn.execute(
                    "SELECT DISTINCT module FROM audit_log ORDER BY module"
                ).fetchall()
            return jsonify(modules=[r[0] for r in rows])

        @bp.route("/api/audit/clear", methods=["POST"])
        def clear_audit():
            audit.clear()
            audit.log("audit_log", "clear_log", "ok",
                      remote_ip=request.remote_addr)
            return jsonify(ok=True)

        return bp
