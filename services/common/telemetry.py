import os
import sys
import shutil
import subprocess
import platform
from datetime import datetime, timedelta
from pathlib import Path
from services.common.db import get_config

def get_ram():
    """Retorna dict com memória total, usada e porcentagem (Linux e Windows)."""
    try:
        if platform.system() == "Linux" and os.path.exists("/proc/meminfo"):
            mem = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    p = line.split(":")
                    if len(p) == 2:
                        mem[p[0].strip()] = int(p[1].split()[0])
            total_mb = mem.get("MemTotal", 1) / 1024
            avail_mb = mem.get("MemAvailable", 0) / 1024
            used_mb = total_mb - avail_mb
            pct = (used_mb / total_mb) * 100
            return {
                "total_gb": round(total_mb / 1024, 2),
                "used_gb": round(used_mb / 1024, 2),
                "percent": int(pct),
                "text": f"{used_mb/1024:.2f}GB / {total_mb/1024:.2f}GB ({pct:.0f}%)"
            }
        else:
            # Fallback para Windows usando ctypes / GlobalMemoryStatusEx
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_uint),
                    ("dwMemoryLoad", ctypes.c_uint),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            total_gb = stat.ullTotalPhys / (1024**3)
            used_gb = (stat.ullTotalPhys - stat.ullAvailPhys) / (1024**3)
            return {
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "percent": int(stat.dwMemoryLoad),
                "text": f"{used_gb:.2f}GB / {total_gb:.2f}GB ({stat.dwMemoryLoad}%)"
            }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "percent": 0, "text": "N/A"}

def get_cpu():
    """Retorna carga de CPU formatada."""
    try:
        if hasattr(os, "getloadavg"):
            l1, l5, _ = os.getloadavg()
            return {"load1": round(l1, 2), "load5": round(l5, 2), "text": f"{l1:.2f} (1m) / {l5:.2f} (5m)"}
        return {"load1": 0, "load5": 0, "text": "Ativo"}
    except Exception:
        return {"load1": 0, "load5": 0, "text": "N/A"}

def get_disk(path="/"):
    """Retorna espaço em disco."""
    try:
        check_path = "C:\\" if platform.system() == "Windows" else "/"
        d = shutil.disk_usage(check_path)
        free_gb = d.free / (1024**3)
        total_gb = d.total / (1024**3)
        pct = (d.used / d.total) * 100
        return {
            "free_gb": round(free_gb, 1),
            "total_gb": round(total_gb, 1),
            "percent": int(pct),
            "text": f"{free_gb:.1f}GB livres de {total_gb:.1f}GB ({pct:.0f}% em uso)"
        }
    except Exception:
        return {"free_gb": 0, "total_gb": 0, "percent": 0, "text": "N/A"}

def get_uptime():
    """Retorna tempo de atividade formatado."""
    try:
        if platform.system() == "Linux" and os.path.exists("/proc/uptime"):
            with open("/proc/uptime", "r") as f:
                sec = float(f.readline().split()[0])
            return str(timedelta(seconds=int(sec)))
        elif platform.system() == "Windows":
            import ctypes
            uptime_ms = ctypes.windll.kernel32.GetTickCount64()
            return str(timedelta(seconds=int(uptime_ms / 1000)))
        return "N/A"
    except Exception:
        return "N/A"

def check_service(unit_name):
    """Verifica se um serviço systemd está ativo (Linux)."""
    if platform.system() != "Linux":
        return "⚪ Local (Windows)"
    try:
        res = subprocess.run(["systemctl", "is-active", unit_name], capture_output=True, text=True, timeout=2)
        status = res.stdout.strip()
        if status == "active":
            return "🟢 Ativo"
        elif status in ("failed", "inactive", "deactivating"):
            return f"🔴 {status.capitalize()}"
        return f"🟡 {status}"
    except Exception:
        return "⚪ N/A"

def get_docker_containers():
    """Retorna lista de containers Docker rodando."""
    try:
        res = subprocess.run(["docker", "ps", "--format", "{{.Names}}|{{.Status}}"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            containers = []
            for line in res.stdout.strip().split("\n"):
                parts = line.split("|")
                name = parts[0]
                status = parts[1] if len(parts) > 1 else ""
                healthy = "healthy" in status or "Up" in status
                containers.append({"name": name, "status": status, "healthy": healthy})
            return containers
    except Exception:
        pass
    return []

def get_full_telemetry():
    """Compila o relatório completo de telemetria em formato de dicionário."""
    ram = get_ram()
    cpu = get_cpu()
    disk = get_disk()
    uptime = get_uptime()
    sentry_state = get_config("sentry_state", "DISARMED")

    services = {
        "voice": check_service("homeserver-voice"),
        "sentry": check_service("homeserver-sentry"),
        "storage": check_service("homeserver-storage"),
        "telegram": check_service("homeserver-telegram"),
        "api": check_service("homeserver-api")
    }

    return {
        "os": platform.system(),
        "hostname": platform.node(),
        "ram": ram,
        "cpu": cpu,
        "disk": disk,
        "uptime": uptime,
        "sentry_state": sentry_state,
        "services": services,
        "docker_containers": get_docker_containers(),
        "timestamp": datetime.now().isoformat()
    }
