"""
App Store module — Beheer meerdere git bronnen en installeer docker stacks.

Elke bron is een git repo met docker compose stacks.
Bronnen worden beheerd via /api/repos/* en gecached in BASE_DIR/.git-cache/{id}/
"""
from __future__ import annotations
import shutil
import threading
import time
from pathlib import Path

from flask import Blueprint, jsonify, request

from modules.base import ModuleBase
from core import config, jobs, audit, permissions, docker_utils, git_utils


class GitBrowserModule(ModuleBase):
    MODULE_ID   = "git_browser"
    MODULE_NAME = "App Store"
    MODULE_ICON = "🏬"
    MODULE_DESC = "Beheer git bronnen en installeer docker stacks"
    VERSION     = "2.0.0"

    def pages(self):
        return [
            {"id": "git_browser", "label": "App Store", "icon": "🏬",
             "group": "main", "default": True, "dashboard_widget": True},
        ]

    def on_load(self, app) -> None:
        cfg = config.get()
        if not cfg.get("APP_REPOS"):
            return
        interval = int(cfg.get("GIT_AUTO_INTERVAL", 900))
        if interval <= 0:
            return
        t = threading.Thread(target=_auto_sync_loop, args=(interval,), daemon=True)
        t.start()
        print(f"  ⟳ App Store auto-sync gestart (elke {interval}s)")

    def blueprint(self) -> Blueprint:
        bp = Blueprint("git_browser", __name__)

        # ── Repo beheer ───────────────────────────────────────────────────────

        @bp.route("/api/repos")
        def list_repos():
            cfg = config.get()
            repos = cfg.get("APP_REPOS", [])
            # Voeg cache-status toe
            result = []
            for r in repos:
                cloned = git_utils.cache_dir(r["id"]).exists()
                result.append({**r, "cloned": cloned})
            return jsonify(repos=result)

        @bp.route("/api/repos", methods=["POST"])
        def add_repo():
            data = request.json or {}
            url  = data.get("url", "").strip()
            if not url:
                return jsonify(ok=False, msg="URL is verplicht")
            cfg   = config.get()
            repos = list(cfg.get("APP_REPOS", []))
            # Genereer uniek ID
            base_id = url.split("/")[-1].replace(".git", "").replace(" ", "_").lower()[:20]
            rid     = base_id
            existing_ids = {r["id"] for r in repos}
            n = 2
            while rid in existing_ids:
                rid = f"{base_id}_{n}"; n += 1
            repos.append({
                "id":       rid,
                "name":     data.get("name", rid),
                "url":      url,
                "branch":   data.get("branch", "main"),
                "strategy": data.get("strategy", "rebase"),
                "subdir":   data.get("subdir", ""),
            })
            config.update({"APP_REPOS": repos})
            audit.log("git_browser", "add_repo", "ok", details={"id": rid})
            return jsonify(ok=True, id=rid)

        @bp.route("/api/repos/<repo_id>", methods=["PUT"])
        def update_repo(repo_id):
            data  = request.json or {}
            cfg   = config.get()
            repos = list(cfg.get("APP_REPOS", []))
            for i, r in enumerate(repos):
                if r["id"] == repo_id:
                    repos[i] = {**r, **{k: v for k, v in data.items()
                                        if k in ("name", "url", "branch", "strategy")}}
                    config.update({"APP_REPOS": repos})
                    return jsonify(ok=True)
            return jsonify(ok=False, msg="Repo niet gevonden"), 404

        @bp.route("/api/repos/<repo_id>", methods=["DELETE"])
        def delete_repo(repo_id):
            cfg   = config.get()
            repos = [r for r in cfg.get("APP_REPOS", []) if r["id"] != repo_id]
            config.update({"APP_REPOS": repos})
            # Verwijder cache
            cache = git_utils.cache_dir(repo_id)
            if cache.exists():
                shutil.rmtree(str(cache), ignore_errors=True)
            audit.log("git_browser", "delete_repo", "ok", details={"id": repo_id})
            return jsonify(ok=True)

        @bp.route("/api/repos/<repo_id>/clone", methods=["POST"])
        def clone_repo(repo_id):
            cfg  = config.get()
            repo = next((r for r in cfg.get("APP_REPOS", []) if r["id"] == repo_id), None)
            if not repo:
                return jsonify(ok=False, msg="Repo niet gevonden"), 404
            job_id, _ = jobs.create("git_clone", "git_browser")
            jobs.run_in_thread(_clone_job, job_id, repo)
            return jsonify(job_id=job_id)

        @bp.route("/api/repos/<repo_id>/pull", methods=["POST"])
        def pull_repo(repo_id):
            cfg  = config.get()
            repo = next((r for r in cfg.get("APP_REPOS", []) if r["id"] == repo_id), None)
            if not repo:
                return jsonify(ok=False, msg="Repo niet gevonden"), 404
            job_id, _ = jobs.create("git_pull", "git_browser")
            jobs.run_in_thread(_clone_job, job_id, repo)
            return jsonify(job_id=job_id)

        @bp.route("/api/repos/pull-all", methods=["POST"])
        def pull_all():
            cfg   = config.get()
            repos = cfg.get("APP_REPOS", [])
            if not repos:
                return jsonify(ok=False, msg="Geen repos geconfigureerd")
            job_id, _ = jobs.create("git_pull_all", "git_browser")
            jobs.run_in_thread(_pull_all_job, job_id, repos)
            return jsonify(job_id=job_id)

        # ── Stacks ────────────────────────────────────────────────────────────

        @bp.route("/api/git/stacks")
        def list_stacks():
            cfg     = config.get()
            lib_dir = Path(cfg["LIBRARY_DIR"])
            repos   = cfg.get("APP_REPOS", [])
            q       = request.args.get("q", "").lower().strip()
            repo_id = request.args.get("repo", "")

            all_stacks = []
            for repo in repos:
                if repo_id and repo["id"] != repo_id:
                    continue
                stacks = git_utils.scan_stacks(repo["id"], lib_dir, subdir=repo.get("subdir", ""))
                for s in stacks:
                    s["repo_name"] = repo.get("name", repo["id"])
                all_stacks.extend(stacks)

            if q:
                all_stacks = [s for s in all_stacks
                              if q in s["name"].lower() or q in s.get("readme", "").lower()]

            return jsonify(
                stacks=all_stacks,
                repos_cloned=sum(1 for r in repos if git_utils.cache_dir(r["id"]).exists()),
                total_repos=len(repos),
                repo_url="" if len(repos) != 1 else repos[0].get("url", ""),
            )

        @bp.route("/api/git/logo/<repo_id>/<path:stack_path>")
        def stack_logo(repo_id, stack_path):
            """Serveer een repo-logo bestand voor een stack."""
            import mimetypes
            from flask import send_file, abort
            stack_dir = git_utils.cache_dir(repo_id) / stack_path
            for ln in ("logo.svg","logo.png","logo.jpg","logo.webp",
                       "icon.svg","icon.png","icon.jpg"):
                lf = stack_dir / ln
                if lf.exists():
                    mt = mimetypes.guess_type(str(lf))[0] or "image/png"
                    return send_file(str(lf), mimetype=mt,
                                     max_age=3600, conditional=True)
            abort(404)

        @bp.route("/api/git/install", methods=["POST"])
        def install_stack():
            data       = request.json or {}
            stack_path = data.get("path", "")
            repo_id    = data.get("repo_id", "main")
            name       = data.get("name", "")
            env_map    = data.get("env", {})
            cfg        = config.get()
            job_id, _  = jobs.create("stack_install", "git_browser", name)
            jobs.run_in_thread(_install_job, job_id, repo_id, stack_path, name, env_map, cfg)
            return jsonify(job_id=job_id)

        return bp


# ── Job runners ────────────────────────────────────────────────────────────────

def _clone_job(job_id: str, repo: dict):
    q = jobs.get_queue(job_id)
    jobs._jobs[job_id]["status"] = "running"
    jobs.section(q, f"Git: {repo.get('name', repo['id'])}")
    ok, msg = git_utils.clone_or_pull(repo, log_fn=lambda m: jobs.log(q, "dim", m))
    if ok:
        jobs.log(q, "ok", f"✔ {msg or 'Klaar'}")
        audit.log("git_browser", "clone_pull", "ok", details={"repo": repo["id"]})
        jobs.finish(job_id, "done")
    else:
        jobs.error(q, msg)
        audit.log("git_browser", "clone_pull", "error", details=msg)
        jobs.finish(job_id, "error")
    jobs.done(q)


def _pull_all_job(job_id: str, repos: list):
    q = jobs.get_queue(job_id)
    jobs._jobs[job_id]["status"] = "running"
    errors = 0
    for repo in repos:
        jobs.section(q, f"Pull: {repo.get('name', repo['id'])}")
        ok, msg = git_utils.clone_or_pull(repo, log_fn=lambda m: jobs.log(q, "dim", m))
        jobs.log(q, "ok" if ok else "error", msg or ("OK" if ok else "Mislukt"))
        if not ok:
            errors += 1
    jobs.finish(job_id, "done" if not errors else "error")
    jobs.done(q)


def _writable_lib(cfg: dict) -> Path:
    """Geeft een beschrijfbaar library-pad terug.
    Valt terug op /app/data/library als de geconfigureerde map niet beschrijfbaar is.
    """
    lib = Path(cfg.get("LIBRARY_DIR", "/app/data/library"))
    try:
        lib.mkdir(parents=True, exist_ok=True)
        test = lib / ".write_test"
        test.touch(); test.unlink()
        return lib
    except OSError:
        fallback = Path("/app/data/library")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _install_job(job_id: str, repo_id: str, stack_path: str,
                 name: str, env_map: dict, cfg: dict):
    q      = jobs.get_queue(job_id)
    lib    = _writable_lib(cfg)
    data   = Path(cfg.get("DATA_ROOT", "/app/data/stacks-data"))
    jobs._jobs[job_id]["status"] = "running"
    jobs.section(q, f"Installeren: {name}")
    if str(lib) != cfg.get("LIBRARY_DIR", ""):
        jobs.log(q, "warn", f"⚠ LIBRARY_DIR ({cfg.get('LIBRARY_DIR')}) niet beschrijfbaar — "
                            f"installeren naar {lib} (stel paden in via Instellingen → Paden)")
    try:
        src  = git_utils.cache_dir(repo_id) / stack_path
        dest = lib / name
        permissions.ensure_dir(dest)
        shutil.copytree(str(src), str(dest), dirs_exist_ok=True)
        docker_utils.normalize_compose(dest)
        if env_map:
            env_file = dest / ".env"
            if not env_file.exists():
                env_file.write_text(
                    f"# .env voor {name}\n" +
                    "\n".join(f"{k}={v}" for k, v in env_map.items()) + "\n"
                )
        permissions.fix(dest, q)
        permissions.ensure_dir(data / name)
        jobs.log(q, "ok", f"✔ {name} geïnstalleerd → {dest}")
        rc = docker_utils.compose_stream(dest, "up", "--detach", q=q)
        jobs.log(q, "ok" if rc == 0 else "warn",
                 "✔ Container(s) gestart" if rc == 0 else "Start mislukt — check .env")
        audit.log("git_browser", "install_stack", "ok", name, {"repo": repo_id})
        jobs.finish(job_id, "done")
    except Exception as exc:
        jobs.error(q, str(exc))
        audit.log("git_browser", "install_stack", "error", name, str(exc))
        jobs.finish(job_id, "error")
    jobs.done(q)


def _auto_sync_loop(interval: int):
    time.sleep(30)
    while True:
        try:
            cfg = config.get()
            for repo in cfg.get("APP_REPOS", []):
                cache = git_utils.cache_dir(repo["id"])
                if cache.exists():
                    ok, msg = git_utils.clone_or_pull(repo)
                    print(f"  ⟳ Auto-sync {repo['id']}: {'OK' if ok else 'FOUT'} — {msg[:80]}")
        except Exception as e:
            print(f"  ⟳ Auto-sync fout: {e}")
        time.sleep(interval)
