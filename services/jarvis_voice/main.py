import os
import sys
import io
import time
import wave
import sqlite3
import requests
import subprocess
import collections
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
                if line.startswith("export "):
                    line = line[7:].strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip("'").strip('"')
    return env

ENV = load_env()
GROQ_KEY = (
    os.getenv("GROQ_KEY") 
    or os.getenv("GROQ_API_KEY") 
    or ENV.get("GROQ_KEY") 
    or ENV.get("GROQ_API_KEY")
)
AGY_PATH = os.getenv("AGY_PATH") or ENV.get("AGY_PATH", "agy")

RATE = 16000
CHANNELS = 1
CHUNK = 1024

def get_conversation_history(limit=4):
    """Recupera as últimas conversas do SQLite para dar memória contextual à IA."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT transcription, response_text 
            FROM voice_interactions 
            WHERE source='VOICE_ROOM' 
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return ""

        history_lines = ["\n[Contexto das últimas conversas no quarto]:"]
        for r in reversed(rows):
            if r['transcription'] and r['response_text']:
                history_lines.append(f"Usuário: {r['transcription']}")
                history_lines.append(f"Jarvis: {r['response_text']}")
        return "\n".join(history_lines) + "\n"
    except Exception as e:
        print(f"[HISTORY WARN] {e}")
        return ""

def log_interaction(transcription, intent, response, latency_ms):
    """Salva permanentemente a conversa no SQLite para o Diário de Voz e memória contextual."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO voice_interactions (source, transcription, intent_detected, response_text, latency_ms, created_at)
            VALUES ('VOICE_ROOM', ?, ?, ?, ?, datetime('now', 'localtime'))
        """, (transcription, intent, response, latency_ms))
        conn.commit()
        conn.close()
        print(f"[DB] Interação salva com sucesso no banco!")
    except Exception as e:
        print(f"[DB LOG ERROR] Falha ao salvar no banco: {e}")

HALLUCINATIONS = [
    "obrigado",
    "obrigada",
    "obrigado por assistir",
    "obrigada por assistir",
    "deixe seu like",
    "inscreva-se no canal",
    "legendas pela comunidade amara.org",
    "subtitles by",
    "sous-titres",
    "amara.org",
    "you"
]

def transcribe_audio_groq(audio_bytes):
    """Transcreve o áudio gravado utilizando a API Whisper na Groq Cloud SEM prompt para evitar alucinações."""
    if not GROQ_KEY:
        print("[GROQ ERROR] GROQ_KEY não configurada no .env")
        return ""

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}"}
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    # SEM parâmetro 'prompt' para o Whisper jamais alucinar palavras de ativação
    data = {
        "model": "whisper-large-v3",
        "language": "pt",
        "temperature": "0.0"
    }

    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=10)
        if resp.status_code == 200:
            txt = resp.json().get("text", "").strip()
            clean_check = txt.lower().strip(".,!?:; ")
            if clean_check in HALLUCINATIONS or (any(h in clean_check for h in HALLUCINATIONS) and len(clean_check.split()) <= 3):
                print(f"[GROQ] Descartando alucinação de silêncio: \"{txt}\"")
                return ""
            return txt
        else:
            print(f"[GROQ HTTP ERROR] {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[GROQ EXCEPTION] {e}")
    return ""

def ask_jarvis_ai(prompt):
    """Envia pergunta contextualizada com memória para o Gemini via Antigravity CLI."""
    sys_prompt = get_config("system_prompt", "Você é o Jarvis, um assistente inteligente e conciso. Responda de forma direta para fala em voz alta.")
    history = get_conversation_history(limit=4)
    full_prompt = f"{sys_prompt}\n{history}\nUsuário atual: {prompt}\nJarvis:"

    try:
        cmd = [AGY_PATH, "-p", full_prompt, "--dangerously-skip-permissions"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception as e:
        print(f"[AI AGY ERROR] {e}")

    return "Desculpe, não consegui processar a resposta no momento."

def create_wav_bytes(frames):
    """Converte frames de áudio raw PCM em bytes WAV."""
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
    wav_io.seek(0)
    return wav_io.read()

# Apelidos fonéticos precisos (apenas o essencial)
WAKE_ALIASES = ["jarvis", "jardins", "jardim", "jarbas", "computador"]

def flush_audio(stream, ring_buffer):
    """Purga instantaneamente qualquer buffer antigo acumulado no hardware."""
    ring_buffer.clear()
    try:
        stream.stop()
        stream.start()
    except Exception:
        pass

def speak_and_flush(text, stream, ring_buffer):
    """Fala pela caixinha e pausa o microfone para que o Jarvis NUNCA ouça a própria voz."""
    if not text or not text.strip():
        return
    try:
        stream.stop()
    except Exception:
        pass

    speak(text)
    time.sleep(0.4)

    ring_buffer.clear()
    try:
        stream.start()
    except Exception:
        pass

def main():
    print("==================================================")
    print("🎙️ JARVIS VOICE ASSISTANT - CONTÍNUO & BLINDADO")
    print("==================================================")

    configured_wake = [w.strip().lower() for w in get_config("wake_words", "jarvis,computador").split(",")]
    wake_words = list(set(configured_wake + WAKE_ALIASES))
    print(f"[SYSTEM] Palavras de ativação: {wake_words}")

    PRE_ROLL_SECONDS = 0.8
    SILENCE_TIMEOUT = 1.0
    MAX_RECORD_SECONDS = 7.0

    pre_roll_chunks = int((RATE / CHUNK) * PRE_ROLL_SECONDS)
    silence_limit = int((RATE / CHUNK) * SILENCE_TIMEOUT)
    max_chunks = int((RATE / CHUNK) * MAX_RECORD_SECONDS)

    ring_buffer = collections.deque(maxlen=pre_roll_chunks)

    # Mantém o InputStream aberto continuamente
    with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype="int16", blocksize=CHUNK) as stream:
        # Descartar primeiro 0.3s de transiente
        for _ in range(int(RATE / CHUNK * 0.3)):
            stream.read(CHUNK)

        # Calibrar ruído de fundo (1.0 segundo)
        print("[CALIBRATE] Calibrando ruído ambiente do microfone...")
        calib_samples = []
        for _ in range(int(RATE / CHUNK * 1.0)):
            data, _ = stream.read(CHUNK)
            calib_samples.append(np.sqrt(np.mean(data.astype(float)**2)))

        noise_floor = int(np.mean(calib_samples)) if calib_samples else 50
        configured_floor = int(get_config("mic_threshold", "550") or 550)
        # Limiar firme de 550 RMS para imunidade total contra cliques de teclado e ventilador
        threshold = max(configured_floor, int(noise_floor * 3.5), 550)
        print(f"[CALIBRATE] Ruído: {noise_floor} RMS | Limiar Blindado: {threshold} RMS")
        flush_audio(stream, ring_buffer)

        while True:
            try:
                data, _ = stream.read(CHUNK)
                rms = np.sqrt(np.mean(data.astype(float)**2))
                ring_buffer.append(data.tobytes())

                if rms > threshold:
                    start_time = time.time()
                    print(f"\n[VAD] Fala detectada (RMS: {int(rms)} > Limiar: {threshold}). Ouvindo fala...")

                    # Captura o áudio prévio para garantir que "Jarvis" não foi cortado
                    recorded_frames = list(ring_buffer)
                    silent_chunks = 0

                    for _ in range(max_chunks):
                        chunk_data, _ = stream.read(CHUNK)
                        recorded_frames.append(chunk_data.tobytes())
                        chunk_rms = np.sqrt(np.mean(chunk_data.astype(float)**2))

                        if chunk_rms < threshold:
                            silent_chunks += 1
                        else:
                            silent_chunks = 0

                        if silent_chunks > silence_limit and len(recorded_frames) > silence_limit * 2:
                            break

                    duration_sec = len(recorded_frames) * (CHUNK / RATE)
                    print(f"[VAD] Gravação concluída: {duration_sec:.2f}s ({len(recorded_frames)} blocos).")

                    # Ignora barulhinhos/cliques ultracurtos (< 0.4s)
                    if len(recorded_frames) < int((RATE / CHUNK) * 0.4):
                        print("[VAD] Descartado por ser muito curto.")
                        flush_audio(stream, ring_buffer)
                        continue

                    print("[GROQ] Enviando áudio para transcrição Whisper...")
                    audio_bytes = create_wav_bytes(recorded_frames)
                    text = transcribe_audio_groq(audio_bytes)

                    if not text:
                        print("[GROQ] Nenhum texto reconhecido no áudio.")
                        flush_audio(stream, ring_buffer)
                        continue

                    text_lower = text.lower()
                    print(f"[OUVIU] \"{text}\"")

                    # Verificação flexível de palavra de ativação
                    clean_norm = text_lower.replace(".", " ").replace(",", " ").replace("!", " ").replace("?", " ").strip()
                    words_in_text = clean_norm.split()
                    
                    is_wake = any(w in text_lower for w in wake_words) or any(w in words_in_text for w in wake_words)
                    print(f"[CHECK] Palavra de ativação detectada? {is_wake}")
                    if not is_wake:
                        flush_audio(stream, ring_buffer)
                        continue

                    duck_volume(low=True)

                    clean_query = clean_norm
                    for w in sorted(wake_words, key=len, reverse=True):
                        clean_query = clean_query.replace(w, "")
                    clean_query = clean_query.strip(" ,.?!")

                    # 1. Se chamou apenas o nome sem comando
                    if not clean_query or len(clean_query) <= 3:
                        resp = "Sim, senhor. Às suas ordens."
                        print(f"[RESPOSTA] {resp}")
                        speak_and_flush(resp, stream, ring_buffer)
                        log_interaction(text, "WAKE_ONLY", resp, int((time.time() - start_time) * 1000))
                        duck_volume(low=False)
                        continue

                    # 2. Comando de PARAR MÚSICA / PAUSAR (Prioridade Máxima)
                    stop_keywords = ["para", "parar", "pare", "silêncio", "silencio", "pausa", "pausar", "stop", "quieto", "chega", "cancela"]
                    if any(sw in clean_query for sw in stop_keywords) and (any(m in clean_query for m in ["musica", "música", "som", "reprodução", "tocar", "video", "vídeo"]) or clean_query in stop_keywords):
                        print("[CMD] Interrompendo áudio/música imediatamente.")
                        stop_music()
                        resp = "Música pausada."
                        speak_and_flush(resp, stream, ring_buffer)
                        log_interaction(text, "STOP_MUSIC", resp, int((time.time() - start_time) * 1000))
                        continue

                    # 3. Consulta de Horas
                    if any(h in clean_query for h in ["que horas são", "que hora é", "hora atual", "horas agora"]):
                        current_time = time.strftime("%H e %M")
                        resp = f"Agora são {current_time}."
                        speak_and_flush(resp, stream, ring_buffer)
                        log_interaction(text, "TIME_QUERY", resp, int((time.time() - start_time) * 1000))
                        duck_volume(low=False)
                        continue

                    # 4. Tocar Música no YouTube
                    play_prefixes = ["toca ", "toque ", "tocar ", "play ", "bota ", "coloque "]
                    is_music = False
                    music_query = ""
                    for pt in play_prefixes:
                        if clean_query.startswith(pt) or f" {pt}" in clean_query:
                            idx = clean_query.find(pt) + len(pt)
                            music_query = clean_query[idx:].strip()
                            is_music = True
                            break

                    if is_music and music_query and len(music_query) <= 60 and "desculpe" not in music_query:
                        resp = f"Tocando {music_query} agora."
                        print(f"[MÚSICA] {resp}")
                        speak_and_flush(resp, stream, ring_buffer)
                        play_music_youtube(music_query)
                        log_interaction(text, "PLAY_MUSIC", resp, int((time.time() - start_time) * 1000))
                        continue

                    # 5. Raciocínio com IA (Gemini Flash)
                    if len(clean_query) > 3 and "desculpe" not in clean_query:
                        print(f"[IA] Raciocinando com memória contextual: \"{clean_query}\"...")
                        resp = ask_jarvis_ai(clean_query)
                        print(f"[RESPOSTA] {resp}")
                        speak_and_flush(resp, stream, ring_buffer)
                        log_interaction(text, "CHAT_AI", resp, int((time.time() - start_time) * 1000))
                        duck_volume(low=False)
                        continue

                    flush_audio(stream, ring_buffer)

            except KeyboardInterrupt:
                print("\n[INFO] Assistente de voz finalizado.")
                break
            except Exception as e:
                print(f"[VOICE ERROR] {e}")
                time.sleep(0.5)

if __name__ == "__main__":
    main()
