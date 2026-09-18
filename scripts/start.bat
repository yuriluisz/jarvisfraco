@echo off
TITLE JarvisFraco Launcher
cd /d "%~dp0\.."

echo ======================================================
echo 🤖 INICIANDO JARVISFRACO NO WINDOWS...
echo ======================================================

IF NOT EXIST "venv" (
    echo [ERRO] Ambiente virtual nao encontrado! Execute scripts\setup.ps1 primeiro.
    pause
    exit /b 1
)

:: Inicia a Micro-API / Dashboard Web em segundo plano
start "Jarvis API & Web" /min venv\Scripts\python.exe services\api\server.py

:: Inicia o Bot do Telegram
start "Jarvis Telegram" /min venv\Scripts\python.exe services\telegram_bot\bot.py

:: Inicia o Assistente de Voz
start "Jarvis Voice" venv\Scripts\python.exe services\jarvis_voice\main.py

echo.
echo [OK] Todos os modulos foram disparados!
echo Acesse o Painel Web em: http://localhost:8000
echo.
pause
