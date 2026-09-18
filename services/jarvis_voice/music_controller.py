import os
import sys
import json
import time
import subprocess
import platform
from pathlib import Path

SOCKET_PATH = "/tmp/mpv-socket" if platform.system() != "Windows" else r"\\.\pipe\mpv-pipe"

def send_mpv_command(command_list):
    """Envia comandos JSON para o mpv via socket IPC."""
    if platform.system() == "Windows":
        return False # Ducking simplificado no Windows
    if not os.path.exists(SOCKET_PATH):
        return False
    try:
        cmd_json = json.dumps({"command": command_list}) + "\n"
        subprocess.run(
            f"echo '{cmd_json}' | socat - {SOCKET_PATH}",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        return False

def duck_volume(low=True):
    """Reduz o volume da música para 20% quando o usuário estiver falando, ou volta para 100%."""
    vol = 20 if low else 100
    send_mpv_command(["set_property", "volume", vol])

def stop_music():
    """Encerra a reprodução do player de música mpv e yt-dlp."""
    try:
        if platform.system() == "Windows":
            subprocess.run("taskkill /F /IM mpv.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run("taskkill /F /IM yt-dlp.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run("pkill -9 -f 'mpv'", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run("pkill -9 -f 'yt-dlp'", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(SOCKET_PATH):
                try:
                    os.remove(SOCKET_PATH)
                except Exception:
                    pass
        return "Música pausada."
    except Exception:
        return "Nenhuma música tocando."

def play_music_youtube(query):
    """Executa streaming de áudio do YouTube usando o pipe direto yt-dlp | mpv."""
    stop_music()
    time.sleep(0.3)
    try:
        yt_bin = "yt-dlp"
        mpv_bin = "mpv"

        # Pipe de streaming em alta velocidade
        if platform.system() == "Windows":
            cmd = f'{yt_bin} -f bestaudio -o - "ytsearch1:{query}" | {mpv_bin} --no-video --volume=100 -'
        else:
            cmd = f"{yt_bin} -f bestaudio -o - 'ytsearch1:{query}' | {mpv_bin} --no-video --input-ipc-server={SOCKET_PATH} --volume=100 -"

        subprocess.Popen(cmd, shell=True)
        return f"Tocando {query} agora."
    except Exception as e:
        return f"Erro ao buscar no YouTube: {e}"

if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "lofi hip hop"
    print(play_music_youtube(q))
