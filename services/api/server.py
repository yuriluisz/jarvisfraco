import os
import sys
import subprocess
import platform
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.common.db import get_db, get_config, set_config, init_db
from services.common.telemetry import get_full_telemetry

app = FastAPI(title="JarvisFraco Control API", version="1.0.0")

# Habilita CORS para permitir que o index.html seja aberto direto do disco ou de outro servidor
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

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/api/status")
def api_status():
    """Retorna telemetria completa de recursos, serviços e sentinela."""
    return get_full_telemetry()

@app.get("/api/interactions")
def api_interactions(limit: int = 50):
    """Retorna histórico de transcrições e respostas do diário de voz."""
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
def api_get_config():
    """Retorna todas as configurações salvas em system_config."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT key, value, description, updated_at FROM system_config")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"configs": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
def api_set_config(req: ConfigUpdateRequest):
    """Atualiza uma chave de configuração no SQLite."""
    try:
        set_config(req.key, req.value, req.description)
        return {"status": "success", "key": req.key, "value": req.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/services/{service_name}/restart")
def api_restart_service(service_name: str):
    """Reinicia um serviço no Linux via systemctl."""
    allowed = ["homeserver-voice", "homeserver-telegram", "homeserver-sentry", "homeserver-storage", "homeserver-api"]
    if service_name not in allowed:
        raise HTTPException(status_code=400, detail="Serviço não autorizado.")

    if platform.system() == "Linux":
        try:
            subprocess.run(["sudo", "systemctl", "restart", service_name], timeout=5)
            return {"status": "success", "message": f"Serviço {service_name} reiniciado."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao reiniciar: {e}")
    else:
        return {"status": "info", "message": "Reinicialização de serviços em segundo plano só suportada no Linux."}

@app.get("/api/files/search")
def api_search_files(q: str = Query(..., min_length=1)):
    """Busca em texto pleno (FTS5) no catálogo de arquivos organizados."""
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/download")
def api_download_file(path: str):
    """Permite download direto de arquivos catalogados."""
    target = Path(path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(str(target), filename=target.name)

# Monta arquivos estáticos do frontend (web/)
WEB_DIR = BASE_DIR / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

def run():
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))
    print(f"[API] JarvisFraco Control API rodando em http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run()
