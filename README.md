# 🤖 jarvisfraco

<div align="center">

![Platform](https://img.shields.io/badge/Plataforma-Linux%20%7C%20Windows-blue?style=for-the-badge&logo=linux)
![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen?style=for-the-badge&logo=python)
![Hardware](https://img.shields.io/badge/Hardware%20Mínimo-Celeron%20%2B%204GB%20RAM-orange?style=for-the-badge)
![API Cost](https://img.shields.io/badge/Custo%20de%20API-R%24%200%2C00-emerald?style=for-the-badge)
![License](https://img.shields.io/badge/Licença-MIT-purple?style=for-the-badge)

<p align="center">
  <b>Transforme qualquer PC antigo, notebook encostado ou placa-mãe modesta em um Home Server de Inteligência Artificial 24/7 completo, autônomo e de alta eficiência.</b>
</p>

</div>

---

## 💡 Sobre o Projeto

O **`jarvisfraco`** nasceu de um desafio real de engenharia: transformar uma placa-mãe antiga **BAT-I (SoC Intel Celeron J1800 dual-core de 2014, sem instruções AVX/AVX2) com 4GB de RAM** em um assistente residencial e servidor 24/7 de ponta sem gastar **nenhum centavo em APIs de IA** e mantendo o consumo total do sistema operacional e serviços abaixo de **1 GB de RAM**.

O projeto é 100% modular, podendo rodar em uma única máquina ou de forma distribuída (o cérebro em um servidor fraco e a interface em qualquer outro PC, notebook ou celular via rede local).

---

## ✨ Funcionalidades Principais

* 🎙️ **Assistente de Voz Contínuo no Quarto:**
  * Escuta ativa no ambiente com detecção de silêncio (VAD) calibrada dinamicamente.
  * Transcrição ultrarrápida via **Groq Whisper API** (`whisper-large-v3`, ~200ms, free tier).
  * Síntese de fala neural natural em português brasileiro via **Microsoft Edge-TTS** (`pt-BR-AntonioNeural`).
  * Player de música via **YouTube Streaming** (`yt-dlp` + `mpv`) com ducking automático de volume ao falar.
* 📱 **Controle Remoto Total via Telegram:**
  * `/status`: Telemetria em tempo real (CPU, RAM, Disco, Uptime, saúde dos serviços e containers).
  * `/foto`: Tira foto ao vivo da webcam USB e envia na hora.
  * `/armar` e `/desarmar`: Controle do modo Sentinela.
  * `/tocar <música>` e `/parar`: Controle do player de som do quarto.
  * Busca inteligente de arquivos por texto com envio do documento direto para download no chat.
* 👁️ **Sentinela de Presença e Segurança:**
  * Monitoramento inteligente via webcam USB com OpenCV (*frame differencing*).
  * Quando armado, qualquer movimento no quarto tira fotos e envia alerta imediato para o seu Telegram.
  * Câmera liberada quando desarmado para garantia total de privacidade.
* 📂 **Armazenamento Inteligente (Samba + IA):**
  * Pasta de entrada monitorada em tempo real via `watchdog`.
  * Classificação e catalogação automática por IA em categorias (`Documentos`, `Fotos`, `Mídia`, `ISOs`).
  * Banco de dados SQLite centralizado em modo WAL com motor de busca textual em alta velocidade (**FTS5**).
* 🖥️ **Dashboard Web HUD Zero-Dependências:**
  * Interface moderna SPA em **HTML5 + Tailwind CSS (via CDN) + JavaScript vanilla**.
  * **Zero Node.js, zero npm install e zero peso em repouso**.
  * Acompanhamento de telemetria, diário do que a IA ouviu, editor de personalidade e busca de arquivos pelo navegador.
* 🐳 **Streaming de Mídia Local (Docker):**
  * Receita pronta com **Jellyfin** (Direct Play configurado para zero consumo de CPU) e **Dockge**.

---

## 🏛️ Arquitetura do Sistema

```text
                     ┌──────────────────────────────┐
                     │   Dashboard Web SPA (HTML)   │
                     │    http://<servidor>:8000    │
                     └──────────────┬───────────────┘
                                    │ (fetch REST)
                                    ▼
┌───────────────────────────────────────────────────────────────────┐
│                     JARVIS CONTROL API (FastAPI)                  │
└───────┬──────────────┬──────────────┬──────────────┬──────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐
│  Assistente  ││   Sentinela  ││ Bot Telegram ││    Storage   │
│    de Voz    ││    Webcam    ││   (Polling)  ││   Watchdog   │
└───────┬──────┘└───────┬──────┘└───────┬──────┘└───────┬──────┘
        │               │               │               │
        └───────────────┼───────────────┼───────────────┘
                        ▼               ▼
        ┌───────────────────────────────────────────────┐
        │       SQLite Centralizado (WAL + FTS5)        │
        │             data/server.db                    │
        └───────────────────────────────────────────────┘
```

---

## 🚀 Como Começar em 2 Minutos

### 🐧 No Linux (Debian, Ubuntu, Raspberry Pi OS)

Abra o terminal e execute:

```bash
git clone https://github.com/SEU_USUARIO/jarvisfraco.git
cd jarvisfraco
bash scripts/setup.sh
```

O instalador irá:
1. Instalar todas as dependências nativas (`ffmpeg`, `mpv`, `socat`, `python3-venv`).
2. Criar o ambiente virtual e instalar o `requirements.txt`.
3. Aplicar as proteções para o Linux não dormir a tela nem suspender o som.
4. Parametrizar e registrar os 5 serviços do Jarvis no `systemd` para inicialização autônoma 24/7.

Para ativar todos os serviços em segundo plano:
```bash
sudo systemctl enable --now homeserver-api homeserver-telegram homeserver-voice homeserver-sentry homeserver-storage
```

---

### 🪟 No Windows (10 ou 11)

Abra o PowerShell como Administrador na pasta do projeto:

```powershell
git clone https://github.com/SEU_USUARIO/jarvisfraco.git
cd jarvisfraco
.\scripts\setup.ps1
```

Para iniciar o Jarvis no Windows:
* Dê **dois cliques no arquivo `scripts\start.bat`** ou rode `.\scripts\start.ps1`.
* Acesse o Painel de Controle pelo navegador em: **`http://localhost:8000`**.

---

## ⚙️ Configuração (.env)

Copie o modelo de ambiente e preencha suas chaves:

```bash
cp .env.example .env
```

| Variável | Onde Obter / Descrição |
| :--- | :--- |
| `GROQ_KEY` | Chave gratuita em [console.groq.com](https://console.groq.com) (Whisper STT). |
| `TELEGRAM_BOT_TOKEN` | Token criado pelo [@BotFather](https://t.me/BotFather) no Telegram. |
| `ADMIN_CHAT_ID` | Seu ID numérico do Telegram (obtenha com [@userinfobot](https://t.me/userinfobot)). |
| `AGY_PATH` | Caminho do Antigravity CLI ou comando de IA do Gemini. |
| `MIC_THRESHOLD` | Limiar RMS de sensibilidade do microfone (padrão: `200`). |

---

## 📊 Benchmark Real (Hardware Fraco)

Testado em uma placa-mãe **BAT-I SoC Intel Celeron J1800 (2 núcleos @ 2.41 GHz) com 4 GB DDR3L**:

| Componente | Consumo em Repouso | Consumo em Pico |
| :--- | :--- | :--- |
| **Debian 13 (XFCE + LightDM)** | ~420 MB RAM | ~480 MB RAM |
| **Jarvis Daemons (5 serviços Python)** | ~180 MB RAM | ~280 MB RAM |
| **Docker (Jellyfin + Dockge)** | ~120 MB RAM | ~220 MB RAM |
| **Total de Memória Utilizada** | **~720 MB RAM** | **~980 MB RAM** |
| **Memória Livre Restante** | **> 3 GB Livres** | **> 2.8 GB Livres** |

---

## 🤝 Contribuições

Contribuições são muito bem-vindas! Sinta-se à vontade para abrir uma *Issue* ou enviar um *Pull Request*.

1. Faça um Fork do projeto
2. Crie sua branch de feature (`git checkout -b feature/NovaFeature`)
3. Faça commit das alterações (`git commit -m 'feat: Adiciona NovaFeature'`)
4. Envie para o branch (`git push origin feature/NovaFeature`)
5. Abra um Pull Request

---

## 📜 Licença

Distribuído sob a licença MIT. Veja `LICENSE` para mais detalhes.
