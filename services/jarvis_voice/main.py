import os
import sys
import io
import time
import wave
import requests
import subprocess
import numpy as np
import sounddevice as sd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.common.db import get_db, get_config, set_config
from services.jarvis_voice.tts_engine import speak
from services.jarvis_voice.music_controller import play_music_youtube, stop_music, duck_volume

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
GROQ_KEY = os.getenv("GROQ_KEY") or ENV.get("GROQ_KEY")
AGY_PATH = os.getenv("AGY_PATH") or ENV.get("AGY_PATH", "agy")

RATE = 16000
CHANNELS = 1
CHUNK = 1024

def transcribe_audio_groq(audio_bytes):
    """Envia o áudio gravado para a API gratuita do Whisper na Groq Cloud."""
    if not GROQ_KEY:
        print("[GROQ ERROR] Chave GROQ_KEY não configurada no .env")
        return ""

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}"}
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    data = {"model": "whisper-large-v3", "language": "pt"}

    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("text", "").strip()
        else:
            print(f"[GROQ HTTP ERROR] {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[GROQ EXCEPTION] {e}")
    return ""

def ask_jarvis_ai(prompt):
    """Envia pergunta para o cérebro do Jarvis (Antigravity CLI / Gemini)."""
    sys_prompt = get_config("system_prompt", "Você é o Jarvis, um assistente inteligente e conciso. Responda de forma direta para fala em voz alta.")
    full_prompt = f"{sys_prompt}\n\nUsuário: {prompt}\nJarvis:"

    try:
        cmd = [AGY_PATH, "-p", full_prompt, "--dangerously-skip-permissions"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception as e:
        print(f"[AI AGY ERROR] {e}")

    return "Desculpe, não consegui processar a resposta no momento."

def record_speech_vad(threshold, max_seconds=10, silence_timeout=0.8):
    """Grava o áudio do microfone a partir do limiar e para após silêncio."""
    frames = []
    silent_chunks = 0
    silence_limit = int((RATE / CHUNK) * silence_timeout)
    max_chunks = int((RATE / CHUNK) * max_seconds)

    with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype="int16", blocksize=CHUNK) as stream:
        for _ in range(max_chunks):
            data, _ = stream.read(CHUNK)
            frames.append(data.tobytes())
            rms = np.sqrt(np.mean(data.astype(float)**2))

            if rms < threshold:
                silent_chunks += 1
            else:
                silent_chunks = 0

            if silent_chunks > silence_limit and len(frames) > silence_limit * 2:
                break

    # Gera buffer WAV em memória
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
    wav_io.seek(0)
    return wav_io.read()

def calibrate_noise():
    """Calibra o ruído ambiente do quarto para ajustar o limiar."""
    print("[CALIBRATE] Calibrando ruído ambiente do microfone...")
    samples = []
    try:
        with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype="int16", blocksize=CHUNK) as stream:
            for _ in range(int(RATE / CHUNK * 1.5)): # 1.5 segundos
                data, _ = stream.read(CHUNK)
                rms = np.sqrt(np.mean(data.astype(float)**2))
                samples.append(rms)
        noise_floor = int(np.mean(samples)) if samples else 50
        configured_floor = int(get_config("mic_threshold", 200))
        threshold = max(configured_floor, int(noise_floor * 2.2))
        print(f"[CALIBRATE] Ruído: {noise_floor} RMS | Limiar Ativo: {threshold} RMS")
        return threshold
    except Exception as e:
        print(f"[CALIBRATE WARN] Erro na calibração: {e}. Usando limiar padrão 200.")
        return 200

def log_interaction(transcription, intent, response, latency_ms):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO voice_interactions (source, transcription, intent_detected, response_text, latency_ms, created_at)
            VALUES ('VOICE_ROOM', ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (transcription, intent, response, latency_ms))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB LOG ERROR] {e}")

def main():
    print("==================================================")
    print("🎙️ JARVIS VOICE ASSISTANT - OPERACIONAL")
    print("==================================================")

    threshold = calibrate_noise()
    wake_words = [w.strip().lower() for w in get_config("wake_words", "jarvis,computador").split(",")]

    print(f"[SYSTEM] Aguardando palavras de ativação: {wake_words}")

    while True:
        try:
            # Escuta contínua com sounddevice
            with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype="int16", blocksize=CHUNK) as stream:
                data, _ = stream.read(CHUNK)
                rms = np.sqrt(np.mean(data.astype(float)**2))

            if rms > threshold:
                duck_volume(low=True)
                start_time = time.time()
                print(f"\n[VAD] Fala detectada (RMS {int(rms)}). Gravando comando...")

                audio_data = record_speech_vad(threshold)
                text = transcribe_audio_groq(audio_data)

                if not text:
                    duck_volume(low=False)
                    continue

                text_lower = text.lower()
                print(f"[OUVIU] \"{text}\"")

                # Verifica se contém a palavra de ativação
                is_wake = any(w in text_lower for w in wake_words)
                if not is_wake:
                    duck_volume(low=False)
                    continue

                # Remove a palavra de ativação do comando
                clean_query = text_lower
                for w in wake_words:
                    clean_query = clean_query.replace(w, "")
                clean_query = clean_query.strip(",.?! ")

                # Roteamento de intenções
                if any(m in clean_query for m in ["toca ", "toque ", "tocar ", "play "]):
                    music_query = clean_query.replace("toca", "").replace("toque", "").replace("tocar", "").replace("play", "").strip()
                    resp = f"Tocando {music_query} agora."
                    speak(resp)
                    play_music_youtube(music_query)
                    log_interaction(text, "PLAY_MUSIC", resp, int((time.time() - start_time) * 1000))

                elif any(p in clean_query for p in ["para a música", "parar música", "para música", "silêncio", "pausa"]):
                    stop_music()
                    resp = "Música pausada."
                    speak(resp)
                    log_interaction(text, "STOP_MUSIC", resp, int((time.time() - start_time) * 1000))

                elif any(h in clean_query for h in ["que horas são", "hora atual", "horas agora"]):
                    current_time = time.strftime("%H e %M")
                    resp = f"Agora são {current_time}."
                    speak(resp)
                    log_interaction(text, "TIME_QUERY", resp, int((time.time() - start_time) * 1000))
                    duck_volume(low=False)

                else:
                    # Pergunta geral para a IA
                    print(f"[IA] Processando com Gemini: \"{clean_query}\"...")
                    resp = ask_jarvis_ai(clean_query)
                    print(f"[RESPOSTA] {resp}")
                    speak(resp)
                    log_interaction(text, "CHAT_AI", resp, int((time.time() - start_time) * 1000))
                    duck_volume(low=False)

        except KeyboardInterrupt:
            print("\n[INFO] Assistente de voz finalizado.")
            break
        except Exception as e:
            print(f"[VOICE LOOP ERROR] {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
