#!/usr/bin/env bash
# ==============================================================================
# JARVISFRACO - INSTALADOR AUTOMATIZADO PARA LINUX (Debian/Ubuntu/Raspberry Pi)
# ==============================================================================

set -e

echo "======================================================"
echo "🚀 INSTALADOR AUTOMATIZADO - JARVISFRACO"
echo "======================================================"

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CURRENT_USER="$(whoami)"
CURRENT_UID="$(id -u)"

echo "[1/7] Atualizando repositórios e instalando dependências nativas..."
sudo apt-get update
sudo apt-get install -y ffmpeg mpv socat python3 python3-venv python3-pip libasound2-dev alsa-utils sqlite3

echo "[2/7] Desativando economia de tela e proteção de áudio (Estabilidade 24/7)..."
# Desativa suspensão do sistema
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target 2>/dev/null || true

# Desativa economia de energia do chip de áudio
sudo bash -c 'echo "options snd_hda_intel power_save=0 power_save_controller=N" > /etc/modprobe.d/audio_disable_powersave.conf' 2>/dev/null || true
echo 0 | sudo tee /sys/module/snd_hda_intel/parameters/power_save 2>/dev/null || true

# Desativa proteção de tela que corta áudio
sudo apt-get purge -y xfce4-screensaver xscreensaver light-locker 2>/dev/null || true
sudo mkdir -p /etc/X11/xorg.conf.d
sudo bash -c 'cat << "EOF" > /etc/X11/xorg.conf.d/10-dpms.conf
Section "Extensions"
    Option "DPMS" "Disable"
EndSection
Section "ServerFlags"
    Option "BlankTime" "0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime" "0"
    Option "DPMS" "false"
EndSection
EOF' 2>/dev/null || true

# Salva volumes de áudio
amixer set Master 100% unmute 2>/dev/null || true
amixer set Headphone 100% unmute 2>/dev/null || true
amixer set Speaker 100% unmute 2>/dev/null || true
amixer set Capture 100% unmute 2>/dev/null || true
sudo alsactl store 2>/dev/null || true

echo "[3/7] Configurando ambiente virtual Python..."
cd "$CURRENT_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -U yt-dlp

echo "[4/7] Configurando arquivo de ambiente (.env)..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "[AVISO] Arquivo .env criado a partir de .env.example."
    echo "        Por favor, edite o arquivo .env com suas chaves (Groq, Telegram)!"
fi

echo "[5/7] Inicializando banco de dados SQLite..."
python -c "import sys; sys.path.insert(0, '.'); from services.common.db import init_db; init_db()"

echo "[6/7] Configurando permissão de áudio sem interface gráfica (Linger)..."
sudo loginctl enable-linger "$CURRENT_USER" || true
sudo usermod -aG systemd-journal "$CURRENT_USER" || true

echo "[7/7] Gerando e instalando unidades systemd..."
SERVICES=("homeserver-api" "homeserver-telegram" "homeserver-voice" "homeserver-sentry" "homeserver-storage")

for s in "${SERVICES[@]}"; do
    sed -e "s|__USER__|${CURRENT_USER}|g" \
        -e "s|__WORKING_DIR__|${CURRENT_DIR}|g" \
        -e "s|__UID__|${CURRENT_UID}|g" \
        "systemd/${s}.service" | sudo tee "/etc/systemd/system/${s}.service" > /dev/null
done

sudo systemctl daemon-reload

echo "======================================================"
echo "🎉 INSTALAÇÃO DO JARVISFRACO CONCLUÍDA COM SUCESSO!"
echo "======================================================"
echo "Comandos úteis:"
echo "  Iniciar todos os serviços 24/7:"
echo "    sudo systemctl enable --now homeserver-api homeserver-telegram homeserver-voice homeserver-sentry homeserver-storage"
echo ""
echo "  Acessar o Painel de Controle Web:"
echo "    http://localhost:8000 (ou pelo IP da sua rede)"
echo ""
echo "  Verificar status:"
echo "    systemctl status homeserver-*"
echo "======================================================"
