# ==============================================================================
# JARVISFRACO - SCRIPT DE DEPLOY AUTOMATIZADO (WINDOWS -> HOME SERVER)
# ==============================================================================
param(
    [string]$ServerIP = ""
)

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "🚀 DEPLOY DO DASHBOARD & API PARA O HOME SERVER" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

# Solicita o IP do servidor se não for passado como parâmetro
if (-not $ServerIP) {
    $ServerIP = Read-Host "Digite o IP do servidor Jarvis na sua rede local (ex: 192.168.1.100)"
}

if (-not $ServerIP) {
    Write-Host "[ERRO] IP do servidor não informado!" -ForegroundColor Red
    Exit 1
}

$User = "jarvisfracoac"

Write-Host "`n[1/4] Copiando arquivos do Dashboard Web e Micro-API para o servidor ($ServerIP)..." -ForegroundColor Yellow

# Garante diretórios remotos
ssh "$User@$ServerIP" "mkdir -p /opt/homeserver/web /opt/homeserver/services/api /opt/homeserver/services/common"

# Envia os arquivos atualizados via SCP
scp -r "$RepoRoot\web\*" "$User@$ServerIP:/opt/homeserver/web/"
scp -r "$RepoRoot\services\api\*" "$User@$ServerIP:/opt/homeserver/services/api/"
scp -r "$RepoRoot\services\common\*" "$User@$ServerIP:/opt/homeserver/services/common/"

Write-Host "`n[2/4] Instalando dependências (FastAPI e Uvicorn) no servidor..." -ForegroundColor Yellow
ssh "$User@$ServerIP" "/opt/homeserver/venv/bin/pip install fastapi uvicorn"

Write-Host "`n[3/4] Configurando e iniciando o serviço homeserver-api no systemd..." -ForegroundColor Yellow
$remoteCmd = @"
sudo bash -c 'cat << "EOF" > /etc/systemd/system/homeserver-api.service
[Unit]
Description=Jarvis Control API & Web Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$User
WorkingDirectory=/opt/homeserver
ExecStart=/opt/homeserver/venv/bin/python services/api/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF'

sudo systemctl daemon-reload
sudo systemctl enable --now homeserver-api
sudo systemctl restart homeserver-api
"@

ssh "$User@$ServerIP" $remoteCmd

Write-Host "`n[4/4] Verificando status do serviço no servidor..." -ForegroundColor Yellow
ssh "$User@$ServerIP" "systemctl is-active homeserver-api"

Write-Host "======================================================" -ForegroundColor Green
Write-Host "🎉 DEPLOY CONCLUÍDO COM SUCESSO!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host "Abrindo o Dashboard no seu navegador..." -ForegroundColor Cyan
Start-Process "http://$ServerIP:8000"

Write-Host "`nVocê pode acessar o painel a qualquer momento em: http://$ServerIP:8000" -ForegroundColor Yellow
