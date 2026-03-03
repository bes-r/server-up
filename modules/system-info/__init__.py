"""
System Info module — toont CPU, geheugen en schijfruimte van de host.
"""
from __future__ import annotations
import shutil
import subprocess

from flask import Blueprint, jsonify
from modules.base import ModuleBase


class SystemInfoModule(ModuleBase):
    MODULE_ID   = "system_info"
    MODULE_NAME = "System Info"
    MODULE_ICON = "📊"
    MODULE_DESC = "CPU, geheugen en schijfruimte van de host"
    VERSION     = "1.0.0"

    def pages(self):
        return [
            {
                "id":      "system-info",
                "label":   "System Info",
                "icon":    "📊",
                "group":   "system",
                "default": False,
            }
        ]

    def blueprint(self) -> Blueprint:
        bp = Blueprint("system_info", __name__)

        @bp.route("/api/system-info")
        def system_info():
            info = {}

            # Schijfruimte (pad dat in de container zichtbaar is)
            try:
                total, used, free = shutil.disk_usage("/")
                info["disk"] = {
                    "total_gb": round(total / 1e9, 1),
                    "used_gb":  round(used  / 1e9, 1),
                    "free_gb":  round(free  / 1e9, 1),
                    "pct":      round(used / total * 100, 1),
                }
            except Exception as e:
                info["disk"] = {"error": str(e)}

            # Geheugen via /proc/meminfo
            try:
                mem = {}
                for line in open("/proc/meminfo"):
                    k, v = line.split(":")
                    mem[k.strip()] = int(v.strip().split()[0])  # kB
                total_mb = mem.get("MemTotal",  0) // 1024
                free_mb  = mem.get("MemAvailable", 0) // 1024
                used_mb  = total_mb - free_mb
                info["memory"] = {
                    "total_mb": total_mb,
                    "used_mb":  used_mb,
                    "free_mb":  free_mb,
                    "pct":      round(used_mb / total_mb * 100, 1) if total_mb else 0,
                }
            except Exception as e:
                info["memory"] = {"error": str(e)}

            # CPU via /proc/stat (load average)
            try:
                load = open("/proc/loadavg").read().split()
                info["cpu"] = {
                    "load1":  float(load[0]),
                    "load5":  float(load[1]),
                    "load15": float(load[2]),
                }
            except Exception as e:
                info["cpu"] = {"error": str(e)}

            # Uptime
            try:
                secs = float(open("/proc/uptime").read().split()[0])
                d, r = divmod(int(secs), 86400)
                h, r = divmod(r, 3600)
                m    = r // 60
                info["uptime"] = f"{d}d {h}u {m}m" if d else f"{h}u {m}m"
            except Exception:
                info["uptime"] = "?"

            return jsonify(info)

        return bp
