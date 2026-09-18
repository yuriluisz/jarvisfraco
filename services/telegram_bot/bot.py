import os
import sys
import time
import requests
import sqlite3
import subprocess
from pathlib import Path

# Adiciona raiz do projeto ao sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.common.db import get_db, get_config, set_config
from services.common.telemetry import get_full_telemetry
from services.jarvis_voice.music_controller import play_music_youtube, stop_music

def load_env(path=None):
    env_file = Path(path) if path else BASE_DIR / ".env"
    env = {}
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip("'").strip('"')
    return env

ENV_VARS = load_env()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or ENV_VARS.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID") or ENV_VARS.get("ADMIN_CHAT_ID")
API_URL = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""

def send_message(chat_id, text, parse_mode="Markdown"):
    if not API_URL:
        return
    url = f"{API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[ERROR] send_message: {e}")

def send_photo(chat_id, photo_path, caption=""):
    if not API_URL:
        return
    url = f"{API_URL}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": chat_id, "caption": caption}
            requests.post(url, files=files, data=data, timeout=15)
    except Exception as e:
        send_message(chat_id, f"❌ Erro ao enviar foto: {e}")

def handle_foto(chat_id):
    snap_path = Path("/tmp/telegram_snapshot.jpg") if os.name != "nt" else BASE_DIR / "data" / "snapshot.jpg"
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    send_message(chat_id, "📸 Capturando imagem da webcam...")
    
    # Tenta via OpenCV headless primeiro
    captured = False
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(str(snap_path), frame)
                captured = True
            cap.release()
    except Exception:
        pass

    # Fallback para ffmpeg se OpenCV não capturar
    if not captured:
        cmd = f"ffmpeg -f v4l2 -video_size 1280x720 -i /dev/video0 -frames:v 1 -y {snap_path}"
        subprocess.run(cmd, shell=True, capture_output=True)
        if not snap_path.exists():
            cmd = f"ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 -y {snap_path}"
            subprocess.run(cmd, shell=True, capture_output=True)

    if snap_path.exists():
        send_photo(chat_id, str(snap_path), caption=f"📸 Snapshot da Webcam - {time.strftime('%H:%M:%S')}")
    else:
        send_message(chat_id, "❌ Falha ao capturar webcam. Verifique se o dispositivo está conectado.")

def search_and_send_file(chat_id, query):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT filepath, filename, category, ai_summary 
        FROM storage_catalog_fts 
        WHERE storage_catalog_fts MATCH ? 
        LIMIT 1
    """, (query,))
    row = cur.fetchone()
    conn.close()
    
    if row and os.path.exists(row['filepath']):
        filepath = row['filepath']
        filename = row['filename']
        summary = row['ai_summary'] or "Arquivo localizado no catálogo."
        send_message(chat_id, f"📄 Encontrei: *{filename}*\nCategoria: _{row['category']}_\n_{summary}_")
        url = f"{API_URL}/sendDocument"
        try:
            with open(filepath, "rb") as doc:
                files = {"document": doc}
                data = {"chat_id": chat_id}
                requests.post(url, files=files, data=data, timeout=30)
        except Exception as e:
            send_message(chat_id, f"❌ Erro ao enviar documento: {e}")
    else:
        send_message(chat_id, f"🔍 Nenhum arquivo encontrado para: \"{query}\"")

def handle_status(chat_id):
    t = get_full_telemetry()
    sentry_icon = "🛡️ ARMED" if t["sentry_state"] == "ARMED" else "🟢 DISARMED"

    containers_text = "\n".join([f"  • {'🟢' if c['healthy'] else '🟡'} *{c['name']}*: `{c['status']}`" for c in t["docker_containers"]])
    if not containers_text:
        containers_text = "  • ⚪ Nenhum container ativo"

    msg = (
        f"🤖 *STATUS DO JARVIS HOME SERVER*\n\n"
        f"📊 *Recursos do Sistema:*\n"
        f"  • CPU Load: `{t['cpu']['text']}`\n"
        f"  • RAM: `{t['ram']['text']}`\n"
        f"  • Disco: `{t['disk']['text']}`\n"
        f"  • Uptime: `{t['uptime']}`\n\n"
        f"⚙️ *Módulos do Jarvis:*\n"
        f"  • 🎙️ Voz: {t['services']['voice']}\n"
        f"  • 👁️ Sentinela: {t['services']['sentry']} ({sentry_icon})\n"
        f"  • 📂 Storage: {t['services']['storage']}\n"
        f"  • 🤖 Telegram: {t['services']['telegram']}\n"
        f"  • 🌐 Micro-API: {t['services']['api']}\n\n"
        f"🐳 *Containers Docker:*\n"
        f"{containers_text}"
    )
    send_message(chat_id, msg)

def process_message(msg):
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "").strip()

    if not text:
        return

    # Validação opcional de administrador
    if ADMIN_CHAT_ID and str(chat_id) != str(ADMIN_CHAT_ID):
        print(f"[AUTH] Mensagem ignorada de usuário não-admin: {chat_id}")
        return

    print(f"[MSG] de {chat_id}: {text}")

    if text in ("/start", "/help"):
        help_txt = (
            "🤖 *Jarvis Home Server - Comandos Disponíveis:*\n\n"
            "• `/status` - Telemetria em tempo real, serviços e containers\n"
            "• `/foto` - Tira uma foto ao vivo da webcam\n"
            "• `/armar` - Liga o Sentinela de movimento\n"
            "• `/desarmar` - Desliga o Sentinela de movimento\n"
            "• `/tocar <nome>` - Toca música no quarto (YouTube)\n"
            "• `/parar` - Para a reprodução de música\n\n"
            "💡 _Envie qualquer palavra-chave para buscar e baixar arquivos da inbox!_"
        )
        send_message(chat_id, help_txt)

    elif text == "/status":
        handle_status(chat_id)

    elif text == "/foto":
        handle_foto(chat_id)

    elif text == "/armar":
        set_config("sentry_state", "ARMED", "Sentinela de presença")
        send_message(chat_id, "🛡️ *Sentinela ARMADO!* Qualquer movimento enviará fotos de alerta.")

    elif text == "/desarmar":
        set_config("sentry_state", "DISARMED", "Sentinela de presença")
        send_message(chat_id, "🟢 *Sentinela DESARMADO.* Monitoramento de câmera em repouso.")

    elif text.startswith("/tocar "):
        query = text.replace("/tocar ", "").strip()
        send_message(chat_id, f"🎶 Buscando e tocando: *{query}*...")
        res = play_music_youtube(query)
        print(f"[MUSIC] {res}")

    elif text == "/parar":
        res = stop_music()
        send_message(chat_id, f"⏹️ {res}")

    else:
        # Busca inteligente de arquivos indexados
        search_and_send_file(chat_id, text)

def main():
    if not TOKEN:
        print("[AVISO] TELEGRAM_BOT_TOKEN não configurado no .env. Configure para usar o Telegram.")
        return

    print("[INFO] Bot Jarvis operacional com polling nativo iniciado...")
    offset = 0
    while True:
        try:
            url = f"{API_URL}/getUpdates"
            params = {"offset": offset, "timeout": 30}
            resp = requests.get(url, params=params, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("result", []):
                    offset = item["update_id"] + 1
                    if "message" in item:
                        process_message(item["message"])
            else:
                time.sleep(2)
        except requests.exceptions.RequestException:
            time.sleep(3)
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
