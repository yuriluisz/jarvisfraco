import os
import sys
import shutil
import sqlite3
import subprocess
import platform
from pathlib import Path
from datetime import timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
DB_PATH = BASE_DIR / "data" / "server.db"

app = FastAPI(title="Jarvis Control API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConfigUpdateRequest(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def check_service(unit_name):
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

@app.on_event("startup")
def init_defaults():
    try:
        conn = get_db()
        cur = conn.cursor()
        defaults = [
            ("system_prompt", "Você é o Jarvis, um assistente de IA altamente técnico, inteligente e direto. Responda com concisão para saída de voz.", "Prompt da IA"),
            ("assistant_name", "Jarvis", "Nome falado"),
            ("wake_words", "jarvis,computador", "Palavras de ativação"),
            ("sentry_state", "DISARMED", "Estado do sentinela"),
            ("mic_threshold", "200", "Sensibilidade do microfone"),
            ("tts_voice", "pt-BR-AntonioNeural", "Voz neural")
        ]
        for k, v, d in defaults:
            cur.execute("INSERT OR IGNORE INTO system_config (key, value, description) VALUES (?, ?, ?)", (k, v, d))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB INIT WARN] {e}")

@app.get("/api/status")
def api_status():
    # 1. CPU Load
    try:
        if hasattr(os, "getloadavg"):
            l1, l5, _ = os.getloadavg()
            cpu_text = f"{l1:.2f} (1m) / {l5:.2f} (5m)"
        else:
            cpu_text = "Ativo"
    except Exception:
        cpu_text = "N/A"

    # 2. RAM Info
    try:
        if platform.system() == "Linux" and os.path.exists("/proc/meminfo"):
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    p = line.split(":")
                    if len(p) == 2:
                        mem[p[0].strip()] = int(p[1].split()[0])
            total_mb = mem.get("MemTotal", 1) / 1024
            avail_mb = mem.get("MemAvailable", 0) / 1024
            used_mb = total_mb - avail_mb
            pct_ram = int((used_mb / total_mb) * 100)
            ram_text = f"{used_mb/1024:.2f}GB / {total_mb/1024:.2f}GB ({pct_ram}%)"
        else:
            ram_text = "Ativo"
            pct_ram = 50
    except Exception:
        ram_text = "N/A"
        pct_ram = 0

    # 3. Disco
    try:
        check_dir = "/" if platform.system() != "Windows" else "C:\\"
        d = shutil.disk_usage(check_dir)
        free_gb = round(d.free / (1024**3), 1)
        total_gb = round(d.total / (1024**3), 1)
        pct_disk = int((d.used / d.total) * 100)
    except Exception:
        free_gb = 0
        total_gb = 0
        pct_disk = 0

    # 4. Uptime
    try:
        if platform.system() == "Linux" and os.path.exists("/proc/uptime"):
            with open("/proc/uptime") as f:
                sec = float(f.readline().split()[0])
            uptime_str = str(timedelta(seconds=int(sec)))
        else:
            uptime_str = "Ativo"
    except Exception:
        uptime_str = "N/A"

    # 5. Sentinela
    sentry_state = "DISARMED"
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM system_config WHERE key='sentry_state'")
        row = cur.fetchone()
        if row and row['value']:
            sentry_state = row['value']
        conn.close()
    except Exception:
        pass

    return {
        "os": platform.system(),
        "hostname": platform.node(),
        "cpu": {"text": cpu_text},
        "ram": {"text": ram_text, "percent": pct_ram},
        "disk": {"free_gb": free_gb, "total_gb": total_gb, "percent": pct_disk},
        "uptime": uptime_str,
        "sentry_state": sentry_state,
        "services": {
            "voice": check_service("homeserver-voice"),
            "sentry": check_service("homeserver-sentry"),
            "storage": check_service("homeserver-storage"),
            "telegram": check_service("homeserver-telegram"),
            "api": check_service("homeserver-api")
        },
        "docker_containers": []
    }

@app.get("/api/interactions")
def api_interactions(limit: int = 50):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, source, transcription, intent_detected, response_text, latency_ms, created_at 
            FROM voice_interactions 
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"interactions": rows}
    except Exception as e:
        return {"interactions": []}

@app.get("/api/config")
def api_get_config():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT key, value, description, updated_at FROM system_config")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"configs": rows}
    except Exception as e:
        return {"configs": []}

@app.post("/api/config")
def api_set_config(req: ConfigUpdateRequest):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO system_config (key, value, description, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """, (req.key, req.value, req.description))
        conn.commit()
        conn.close()
        return {"status": "success", "key": req.key, "value": req.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/search")
def api_search_files(q: str = Query(..., min_length=1)):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT filepath, filename, category, ai_summary, file_size, created_at 
            FROM storage_catalog_fts 
            WHERE storage_catalog_fts MATCH ? 
            LIMIT 20
        """, (q,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"results": rows}
    except Exception as e:
        return {"results": []}

@app.get("/api/files/download")
def api_download_file(path: str):
    target = Path(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(str(target), filename=target.name)

WEB_DIR = BASE_DIR / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
