"""
Projects module — beheer van docker compose stacks.
Start, stop, update, backup, remove, .env bewerken.
"""
from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, Response, stream_with_context

from modules.base import ModuleBase
from core import config, jobs, docker_utils, permissions, audit


class ProjectsModule(ModuleBase):
    MODULE_ID   = "projects"
    MODULE_NAME = "Projecten"
    MODULE_ICON = "📦"
    MODULE_DESC = "Beheer docker compose stacks in de library map"
    VERSION     = "1.2.0"

    def pages(self):
        return [
            {"id": "projects", "label": "Projecten", "icon": "📦",
             "group": "main", "default": True, "dashboard_widget": True},
        ]

    def blueprint(self) -> Blueprint:
        bp = Blueprint("projects", __name__)

        @bp.route("/api/projects")
        def list_projects():
            cfg = config.get()
            lib = Path(cfg["LIBRARY_DIR"])
            names = sorted(d.name for d in lib.iterdir() if d.is_dir()) if lib.is_dir() else []
            ps = docker_utils.docker_ps()
            result = []
            for name in names:
                pdir = lib / name
                ps_info = ps.get(name, {})
                running = ps_info.get("running", False)
                installed = bool(ps_info)
                containers = ps_info.get("containers", [])
                ports = []
                for c in containers:
                    import re
                    for m in re.finditer(r":(\d+)->", c.get("ports", "")):
                        ports.append(int(m.group(1)))
                result.append({
                    "name": name,
                    "has_compose": docker_utils.has_compose(pdir),
                    "has_env": (pdir / ".env").exists(),
                    "installed": installed,
                    "running": running,
                    "containers": containers,
                    "ports": sorted(set(ports)),
                })
            return jsonify(result)

        @bp.route("/api/projects/<name>/env", methods=["GET"])
        def get_env(name):
            cfg = config.get()
            env_file = Path(cfg["LIBRARY_DIR"]) / name / ".env"
            return jsonify(content=env_file.read_text() if env_file.exists() else "", exists=env_file.exists())

        @bp.route("/api/projects/<name>/env", methods=["PUT"])
        def set_env(name):
            cfg = config.get()
            pdir = Path(cfg["LIBRARY_DIR"]) / name
            pdir.mkdir(parents=True, exist_ok=True)
            env_file = pdir / ".env"
            env_file.write_text(request.json.get("content", ""))
            env_file.chmod(0o600)
            audit.log("projects", "edit_env", "ok", name, remote_ip=request.remote_addr)
            return jsonify(ok=True)

        @bp.route("/api/projects/<name>/compose", methods=["GET"])
        def get_compose(name):
            cfg = config.get()
            pdir = Path(cfg["LIBRARY_DIR"]) / name
            cf = docker_utils.find_compose(pdir)
            if not cf:
                return jsonify(content="", exists=False)
            return jsonify(content=cf.read_text(errors="replace"), filename=cf.name, exists=True)

        @bp.route("/api/projects/<name>/compose", methods=["PUT"])
        def set_compose(name):
            cfg = config.get()
            pdir = Path(cfg["LIBRARY_DIR"]) / name
            pdir.mkdir(parents=True, exist_ok=True)
            compose_file = pdir / "docker-compose.yaml"
            compose_file.write_text(request.json.get("content", ""))
            compose_file.chmod(0o644)
            audit.log("projects", "edit_compose", "ok", name, remote_ip=request.remote_addr)
            return jsonify(ok=True)

        # ── Actions ────────────────────────────────────────────────────────────
        for action in ("start", "stop", "restart", "update", "backup", "fix_permissions"):
            bp.add_url_rule(
                f"/api/projects/<name>/{action}",
                f"action_{action}",
                _make_action_handler(action),
                methods=["POST"],
            )

        @bp.route("/api/projects/<name>/remove", methods=["POST"])
        def remove_project(name):
            mode = (request.json or {}).get("mode", "stack")
            job_id, q = jobs.create("remove", "projects", name)
            jobs.run_in_thread(_run_action, job_id, name, "remove", {"mode": mode})
            return jsonify(job_id=job_id)

        @bp.route("/api/projects/<name>/logs")
        def project_logs(name):
            tail = request.args.get("tail", "200")
            job_id, q = jobs.create("logs", "projects", name)
            jobs.run_in_thread(_stream_logs, job_id, name, tail)
            return jsonify(job_id=job_id)

        @bp.route("/api/projects/fix-permissions-all", methods=["POST"])
        def fix_all():
            job_id, q = jobs.create("fix_permissions_all", "projects")
            jobs.run_in_thread(_run_action, job_id, "", "fix_permissions_all", {})
            return jsonify(job_id=job_id)

        return bp


# ── Action functions ───────────────────────────────────────────────────────────

def _make_action_handler(action: str):
    def handler(name):
        job_id, q = jobs.create(action, "projects", name)
        jobs.run_in_thread(_run_action, job_id, name, action, {})
        return jsonify(job_id=job_id)
    handler.__name__ = f"handler_{action}"
    return handler


def _run_action(job_id: str, name: str, action: str, extra: dict):
    cfg   = config.get()
    q     = jobs.get_queue(job_id)
    lib   = Path(cfg["LIBRARY_DIR"])
    pdir  = lib / name if name else lib
    _jobs = jobs

    _jobs.get(job_id) and (_jobs._jobs[job_id].__setitem__("status", "running") if hasattr(_jobs, "_jobs") else None)

    def _set_running():
        j = _jobs._jobs.get(job_id)
        if j: j["status"] = "running"
    _set_running()

    try:
        # Actions that need a project dir
        if action in ("start", "stop", "restart", "update", "fix_permissions", "remove"):
            if not pdir.is_dir():
                jobs.error(q, f"Project map niet gevonden: {pdir}")
                audit.log("projects", action, "error", name)
                return
            docker_utils.normalize_compose(pdir)

        if action == "start":
            jobs.section(q, "Permissies")
            permissions.ensure_dir(pdir)
            permissions.ensure_dir(Path(cfg["DATA_ROOT"]) / name)
            s = permissions.fix(pdir, q)
            jobs.log(q, "ok", f"Permissies: {s['changed']} gewijzigd")
            jobs.section(q, "Starten")
            rc = docker_utils.compose_stream(pdir, "up", "--detach", q=q)
            if rc == 0:
                jobs.log(q, "ok", f"Project '{name}' gestart")
            else:
                jobs.log(q, "error", "docker compose up mislukt")

        elif action == "stop":
            jobs.section(q, "Stoppen")
            rc = docker_utils.compose_stream(pdir, "down", q=q)
            jobs.log(q, "ok" if rc == 0 else "error",
                     f"Project '{name}' gestopt" if rc == 0 else "docker compose down mislukt")

        elif action == "restart":
            jobs.section(q, "Herstarten")
            docker_utils.compose_stream(pdir, "down", q=q)
            rc = docker_utils.compose_stream(pdir, "up", "--detach", q=q)
            jobs.log(q, "ok" if rc == 0 else "error",
                     f"Project '{name}' herstart" if rc == 0 else "Herstart mislukt")

        elif action == "update":
            jobs.section(q, "Images pullen")
            docker_utils.compose_stream(pdir, "pull", q=q)
            jobs.section(q, "Updaten")
            rc = docker_utils.compose_stream(pdir, "up", "--detach", "--remove-orphans", q=q)
            jobs.log(q, "ok" if rc == 0 else "error",
                     f"Project '{name}' bijgewerkt" if rc == 0 else "Update mislukt")

        elif action == "backup":
            jobs.section(q, "Backup")
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            bdir = Path(cfg["BACKUP_ROOT"]) / f"{name}-{ts}"
            permissions.ensure_dir(bdir, permissions.PERM_BACKUP_DIR)
            if pdir.is_dir():
                shutil.copytree(str(pdir), str(bdir / name), dirs_exist_ok=True)
            ddir = Path(cfg["DATA_ROOT"]) / name
            if ddir.is_dir():
                shutil.copytree(str(ddir), str(bdir / f"{name}-data"), dirs_exist_ok=True)
            s = permissions.fix(bdir, q, backup=True)
            jobs.log(q, "ok", f"Backup aangemaakt: {bdir} ({s['changed']} bestanden beveiligd)")

        elif action == "fix_permissions":
            jobs.section(q, "Permissies herstellen")
            permissions.ensure_dir(pdir)
            s = permissions.fix(pdir, q)
            ddir = Path(cfg["DATA_ROOT"]) / name
            if ddir.exists():
                permissions.ensure_dir(ddir)
                ds = permissions.fix(ddir, q)
                jobs.log(q, "ok", f"Data map: {ds['changed']} wijzigingen")
            jobs.log(q, "ok", f"Klaar — {s['changed']} gewijzigd, {s['errors']} fouten")

        elif action == "fix_permissions_all":
            jobs.section(q, "Permissies herstellen voor ALLE projecten")
            cfg2 = config.get()
            names = sorted(d.name for d in lib.iterdir() if d.is_dir()) if lib.is_dir() else []
            total = 0
            for p in names:
                prd = lib / p
                permissions.ensure_dir(prd)
                s = permissions.fix(prd, q)
                total += s["changed"]
            jobs.log(q, "ok", f"Klaar — {total} totale wijzigingen")

        elif action == "remove":
            jobs.section(q, "Verwijderen")
            mode = extra.get("mode", "stack")
            if docker_utils.has_compose(pdir):
                docker_utils.compose_stream(pdir, "down", "-v", q=q)
            if mode in ("full", "all") and pdir.is_dir():
                shutil.rmtree(pdir)
                jobs.log(q, "ok", "Project map verwijderd")
            if mode == "all":
                ddir = Path(cfg["DATA_ROOT"]) / name
                if ddir.is_dir():
                    shutil.rmtree(ddir)
                    jobs.log(q, "ok", "Data map verwijderd")
            jobs.log(q, "ok", f"Project '{name}' verwijderd (mode: {mode})")

        audit.log("projects", action, "ok", name)
        jobs.finish(job_id, "done")
        jobs.done(q)

    except Exception as exc:
        jobs.error(q, str(exc))
        audit.log("projects", action, "error", name, str(exc))
        jobs.finish(job_id, "error")


def _stream_logs(job_id: str, name: str, tail: str):
    import subprocess
    cfg  = config.get()
    q    = jobs.get_queue(job_id)
    pdir = Path(cfg["LIBRARY_DIR"]) / name
    docker_utils.normalize_compose(pdir)
    cmd = docker_utils.COMPOSE + ["logs", "--tail", tail, "-f"]
    try:
        proc = subprocess.Popen(cmd, cwd=str(pdir),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            jobs.log(q, "dim", line.rstrip())
        proc.wait()
    except Exception as e:
        jobs.log(q, "error", str(e))
    q.put(None)
