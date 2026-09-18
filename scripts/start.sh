#!/usr/bin/env bash
# ==============================================================================
# JARVISFRACO - INICIALIZADOR INTERATIVO MANUAL (LINUX)
# ==============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d "venv" ]; then
    echo "[ERRO] Ambiente virtual venv não encontrado. Execute ./scripts/setup.sh primeiro."
    exit 1
fi

source venv/bin/activate

echo "======================================================"
echo "🤖 INICIANDO JARVISFRACO EM MODO INTERATIVO..."
echo "======================================================"

trap 'pkill -P $$; exit' SIGINT SIGTERM EXIT

python services/api/server.py &
python services/telegram_bot/bot.py &
python services/sentry/camera_detector.py &
python services/storage_organizer/main.py &
python services/jarvis_voice/main.py
