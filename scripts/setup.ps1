# ==============================================================================
# JARVISFRACO - INSTALADOR AUTOMATIZADO PARA WINDOWS (PowerShell)
# ==============================================================================

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "🚀 INSTALADOR AUTOMATIZADO - JARVISFRACO (WINDOWS)" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

# 1. Verifica Python
Write-Host "[1/5] Verificando instalação do Python..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERRO] Python não encontrado no PATH! Instale o Python 3.10+ pelo site oficial python.org (marcando a opção 'Add Python to PATH')." -ForegroundColor Red
    Exit 1
}

# 2. Ambiente Virtual
Write-Host "[2/5] Criando e configurando ambiente virtual venv..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
}

& ".\venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\venv\Scripts\python.exe" -m pip install -U yt-dlp

# 3. Verifica Ferramentas de Mídia (FFmpeg e MPV)
Write-Host "[3/5] Verificando FFmpeg e MPV..." -ForegroundColor Yellow
$missing = @()
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { $missing += "Gyan.FFmpeg" }
if (-not (Get-Command mpv -ErrorAction SilentlyContinue)) { $missing += "mpv.net" }

if ($missing.Count -gt 0) {
    Write-Host "[AVISO] Recomendamos instalar as ferramentas de mídia via Winget:" -ForegroundColor Yellow
    Write-Host "  winget install $($missing -join ' ')" -ForegroundColor Gray
}

# 4. Configura .env
Write-Host "[4/5] Configurando arquivo .env..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[AVISO] Arquivo .env criado! Preencha suas credenciais (GROQ_KEY, TELEGRAM_BOT_TOKEN)." -ForegroundColor Cyan
}

# 5. Inicializa Banco SQLite
Write-Host "[5/5] Inicializando banco SQLite..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -c "import sys; sys.path.insert(0, '.'); from services.common.db import init_db; init_db()"

Write-Host "======================================================" -ForegroundColor Green
Write-Host "🎉 JARVISFRACO INSTALADO COM SUCESSO NO WINDOWS!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host "Para iniciar o Jarvis no Windows:" -ForegroundColor Cyan
Write-Host "  Execute: .\scripts\start.bat ou .\scripts\start.ps1" -ForegroundColor Gray
Write-Host "  Abra no navegador: http://localhost:8000" -ForegroundColor Gray
Write-Host "======================================================" -ForegroundColor Green
