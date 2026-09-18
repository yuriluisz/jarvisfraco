import os
import sys
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.common.db import get_db, get_config

def load_env():
    env_file = BASE_DIR / ".env"
    env = {}
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip("'").strip('"')
    return env

ENV = load_env()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or ENV.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID") or ENV.get("ADMIN_CHAT_ID")
API_URL = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""

SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def send_telegram_alert(photo_path, caption):
    if not API_URL or not ADMIN_CHAT_ID:
        return
    url = f"{API_URL}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            requests.post(url, files={"photo": f}, data={"chat_id": ADMIN_CHAT_ID, "caption": caption}, timeout=15)
    except Exception as e:
        print(f"[ALERT ERROR] Falha ao enviar alerta no Telegram: {e}")

def log_sentry_event(event_type, details, snapshot_path):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sentry_logs (event_type, details, snapshot_path, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (event_type, details, str(snapshot_path)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Erro ao gravar sentry_log: {e}")

def main():
    print("[INFO] Serviço Jarvis Sentinela iniciado...")

    try:
        import cv2
    except ImportError:
        print("[ERRO] OpenCV não está instalado. Instale opencv-python-headless.")
        return

    cap = None
    last_frame = None
    last_alert_time = 0
    COOLDOWN_SECONDS = 6

    while True:
        try:
            state = get_config("sentry_state", "DISARMED")

            if state != "ARMED":
                if cap is not None:
                    print("[SENTRY] Desarmado. Liberando câmera para privacidade...")
                    cap.release()
                    cap = None
                    last_frame = None
                time.sleep(3)
                continue

            # Se armado e câmera fechada, inicializa
            if cap is None:
                print("[SENTRY] ARMADO! Inicializando captura de vídeo...")
                cap = cv2.VideoCapture(0)
                time.sleep(1)

            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(1)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if last_frame is None:
                last_frame = gray
                continue

            # Detecção de movimento por diferença de quadros
            frame_delta = cv2.absdiff(last_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            motion_detected = False
            for c in contours:
                if cv2.contourArea(c) > 5000: # Limiar de movimento significativo
                    motion_detected = True
                    break

            last_frame = gray

            now = time.time()
            if motion_detected and (now - last_alert_time > COOLDOWN_SECONDS):
                last_alert_time = now
                timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                snap_file = SNAPSHOTS_DIR / f"alerta_{timestamp_str}.jpg"
                cv2.imwrite(str(snap_file), frame)

                alert_msg = f"🚨 *ALERTA SENTINELA:* Movimento detectado no quarto! Horário: `{time.strftime('%H:%M:%S')}`"
                print(f"[ALERTA] Movimento detectado! Snapshot salvo em: {snap_file}")

                log_sentry_event("MOTION_DETECTED", "Movimento detectado no campo de visão", snap_file)
                send_telegram_alert(snap_file, alert_msg)

            time.sleep(0.1)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[SENTRY LOOP ERROR] {e}")
            time.sleep(2)

    if cap:
        cap.release()

if __name__ == "__main__":
    main()
