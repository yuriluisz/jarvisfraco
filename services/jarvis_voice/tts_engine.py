import os
import sys
import asyncio
import subprocess
import platform
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.common.db import get_config

TTS_FILE = Path("/tmp/jarvis_speech.mp3") if platform.system() != "Windows" else BASE_DIR / "data" / "jarvis_speech.mp3"

async def _synthesize_edge_tts(text, voice):
    import edge_tts
    TTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(TTS_FILE))

def speak(text, voice=None):
    """Sintetiza texto em áudio neural com edge-tts e reproduz na caixinha de som."""
    if not text or not text.strip():
        return

    chosen_voice = voice or get_config("tts_voice", "pt-BR-AntonioNeural")
    try:
        # Gera o áudio neural
        asyncio.run(_synthesize_edge_tts(text, chosen_voice))

        # Reproduz o arquivo
        if platform.system() == "Windows":
            subprocess.run(f'mpv --no-video --volume=100 "{TTS_FILE}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(f'mpv --no-video --volume=100 "{TTS_FILE}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    except Exception as e:
        print(f"[TTS ERROR] Falha na síntese de voz: {e}")

if __name__ == "__main__":
    test_text = sys.argv[1] if len(sys.argv) > 1 else "Olá, eu sou o Jarvis. Todos os sistemas estão operacionais."
    print(f"Falando: {test_text}")
    speak(test_text)
