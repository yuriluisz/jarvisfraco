// ==============================================================================
// JARVISFRACO DASHBOARD - CONTROLLER JAVASCRIPT (VANILLA / 0 DEPENDÊNCIAS)
// ==============================================================================

let API_HOST = localStorage.getItem("jarvis_api_host");

// Se aberto direto do servidor via http://<ip>:8000, usa a própria origem
if (!API_HOST) {
  if (window.location.protocol.startsWith("http")) {
    API_HOST = window.location.origin;
  } else {
    API_HOST = "http://localhost:8000";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const hostInput = document.getElementById("apiHostInput");
  if (hostInput) {
    hostInput.value = API_HOST;
  }

  document.getElementById("saveHostBtn")?.addEventListener("click", () => {
    const val = hostInput.value.trim().replace(/\/+$/, "");
    if (val) {
      API_HOST = val;
      localStorage.setItem("jarvis_api_host", val);
      loadTelemetry();
      alert(`Servidor atualizado para: ${val}`);
    }
  });

  // Inicia carregamento
  loadTelemetry();
  loadConfigs();

  // Polling de telemetria a cada 4 segundos
  setInterval(loadTelemetry, 4000);
});

// Navegação de Abas
function switchTab(tabName) {
  document.querySelectorAll(".tab-content").forEach(el => el.classList.add("hidden"));
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.remove("bg-cyan-950/70", "text-cyan-400", "border-cyan-800");
    btn.classList.add("text-slate-400");
  });

  const activeContent = document.getElementById(`content-${tabName}`);
  const activeBtn = document.getElementById(`tab-${tabName}`);

  if (activeContent) activeContent.classList.remove("hidden");
  if (activeBtn) {
    activeBtn.classList.remove("text-slate-400");
    activeBtn.classList.add("bg-cyan-950/70", "text-cyan-400", "border", "border-cyan-800");
  }

  if (tabName === "voice") loadInteractions();
  if (tabName === "config") loadConfigs();

  if (window.lucide) lucide.createIcons();
}

// 1. Telemetria e Status
async function loadTelemetry() {
  try {
    const res = await fetch(`${API_HOST}/api/status`, { timeout: 3000 });
    if (!res.ok) throw new Error("Falha HTTP");
    const data = await res.json();

    setConnectionStatus(true);

    // Cards
    document.getElementById("cardCpu").textContent = data.cpu.text || "-";
    document.getElementById("cardRam").textContent = data.ram.text || "-";
    document.getElementById("barRam").style.width = `${data.ram.percent}%`;
    document.getElementById("cardDisk").textContent = `${data.disk.free_gb} GB`;
    document.getElementById("cardDiskSub").textContent = `${data.disk.percent}% usado de ${data.disk.total_gb}GB`;
    document.getElementById("cardUptime").textContent = data.uptime || "-";
    document.getElementById("cardHostname").textContent = `Host: ${data.hostname} (${data.os})`;

    // Serviços
    updateServiceBadge("svc-voice", data.services.voice);
    updateServiceBadge("svc-sentry", data.services.sentry);
    updateServiceBadge("svc-storage", data.services.storage);
    updateServiceBadge("svc-telegram", data.services.telegram);

    // Sentinela
    const isArmed = data.sentry_state === "ARMED";
    const sentryText = document.getElementById("sentryText");
    const sentryIcon = document.getElementById("sentryIcon");
    if (sentryText && sentryIcon) {
      sentryText.textContent = isArmed ? "ARMADO (MONITORANDO)" : "DESARMADO (REPOUSO)";
      sentryText.className = isArmed ? "font-mono text-sm font-bold text-red-400" : "font-mono text-sm text-emerald-400";
      sentryIcon.className = isArmed ? "w-3 h-3 rounded-full bg-red-400 animate-ping" : "w-3 h-3 rounded-full bg-emerald-400";
    }

    // Docker Containers
    const dockerList = document.getElementById("dockerList");
    if (dockerList) {
      if (data.docker_containers && data.docker_containers.length > 0) {
        dockerList.innerHTML = data.docker_containers.map(c => `
          <div class="flex items-center justify-between p-2 rounded-lg bg-slate-900 border border-slate-800">
            <span class="text-slate-200">${c.name}</span>
            <span class="${c.healthy ? 'text-emerald-400' : 'text-amber-400'}">${c.status}</span>
          </div>
        `).join("");
      } else {
        dockerList.innerHTML = `<p class="text-slate-500">Nenhum container ativo.</p>`;
      }
    }

  } catch (err) {
    setConnectionStatus(false);
  }
}

function updateServiceBadge(elementId, statusText) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = statusText;
  if (statusText.includes("Ativo")) {
    el.className = "text-xs font-mono font-bold text-emerald-400";
  } else if (statusText.includes("Local")) {
    el.className = "text-xs font-mono text-slate-400";
  } else {
    el.className = "text-xs font-mono font-bold text-red-400";
  }
}

function setConnectionStatus(online) {
  const badge = document.getElementById("connectionBadge");
  const text = document.getElementById("connectionText");
  if (!badge || !text) return;

  if (online) {
    badge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full bg-emerald-950/80 border border-emerald-800/80 text-emerald-400 text-xs font-medium";
    text.textContent = "Conectado";
  } else {
    badge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full bg-red-950/80 border border-red-800/80 text-red-400 text-xs font-medium";
    text.textContent = "Reconectando...";
  }
}

// 2. Diário de Voz (Histórico)
async function loadInteractions() {
  const tbody = document.getElementById("interactionsTableBody");
  if (!tbody) return;

  try {
    const res = await fetch(`${API_HOST}/api/interactions?limit=30`);
    const data = await res.json();
    const rows = data.interactions || [];

    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-slate-500 font-sans">Nenhuma conversa registrada ainda.</td></tr>`;
      return;
    }

    tbody.innerHTML = rows.map(r => `
      <tr class="hover:bg-slate-900/40 transition">
        <td class="px-6 py-4 text-slate-400 whitespace-nowrap">${r.created_at || '-'}</td>
        <td class="px-6 py-4 font-sans text-slate-200 font-medium">${escapeHtml(r.transcription || '')}</td>
        <td class="px-6 py-4 font-sans text-cyan-300">${escapeHtml(r.response_text || '')}</td>
        <td class="px-6 py-4"><span class="px-2 py-0.5 rounded bg-slate-800 text-slate-400">${r.intent_detected || 'CHAT'}</span></td>
        <td class="px-6 py-4 text-slate-500">${r.latency_ms ? r.latency_ms + 'ms' : '-'}</td>
      </tr>
    `).join("");

  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-red-400 font-sans">Erro ao carregar histórico: ${e.message}</td></tr>`;
  }
}

// 3. Configurações & Personalidade
async function loadConfigs() {
  try {
    const res = await fetch(`${API_HOST}/api/config`);
    const data = await res.json();
    const map = {};
    (data.configs || []).forEach(c => { map[c.key] = c.value; });

    if (map.system_prompt) document.getElementById("cfgSystemPrompt").value = map.system_prompt;
    if (map.wake_words) document.getElementById("cfgWakeWords").value = map.wake_words;
    if (map.mic_threshold) document.getElementById("cfgThreshold").value = map.mic_threshold;
    if (map.tts_voice) document.getElementById("cfgVoice").value = map.tts_voice;
  } catch (e) {
    console.error("Erro ao carregar configurações:", e);
  }
}

async function saveSystemPrompt() {
  const val = document.getElementById("cfgSystemPrompt").value;
  await saveConfigKey("system_prompt", val, "Prompt de personalidade da IA");
  alert("Personalidade do Jarvis atualizada com sucesso!");
}

async function saveTuningConfig() {
  const wake = document.getElementById("cfgWakeWords").value;
  const thresh = document.getElementById("cfgThreshold").value;
  const voice = document.getElementById("cfgVoice").value;

  await saveConfigKey("wake_words", wake);
  await saveConfigKey("mic_threshold", thresh);
  await saveConfigKey("tts_voice", voice);

  alert("Parâmetros de áudio e ativação salvos!");
}

async function toggleSentry() {
  try {
    const res = await fetch(`${API_HOST}/api/status`);
    const data = await res.json();
    const newState = data.sentry_state === "ARMED" ? "DISARMED" : "ARMED";
    await saveConfigKey("sentry_state", newState, "Estado do sentinela");
    loadTelemetry();
  } catch (e) {
    alert("Erro ao alternar sentinela: " + e.message);
  }
}

async function saveConfigKey(key, value, description) {
  try {
    await fetch(`${API_HOST}/api/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, value: String(value), description })
    });
  } catch (e) {
    console.error(`Erro ao salvar ${key}:`, e);
  }
}

// 4. Catálogo de Arquivos FTS5
let searchTimer = null;
function handleSearch(e) {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (!q) {
    document.getElementById("searchResults").innerHTML = `<div class="p-8 text-center text-slate-500 font-sans col-span-full">Digite um termo acima para pesquisar.</div>`;
    return;
  }

  searchTimer = setTimeout(async () => {
    try {
      const res = await fetch(`${API_HOST}/api/files/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      const results = data.results || [];
      const container = document.getElementById("searchResults");

      if (results.length === 0) {
        container.innerHTML = `<div class="p-8 text-center text-slate-500 font-sans col-span-full">Nenhum arquivo encontrado para "${escapeHtml(q)}".</div>`;
        return;
      }

      container.innerHTML = results.map(f => `
        <div class="p-5 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col justify-between space-y-4">
          <div>
            <div class="flex items-center justify-between text-xs text-cyan-400 font-mono mb-1">
              <span>${f.category || 'Outros'}</span>
              <span>${formatBytes(f.file_size)}</span>
            </div>
            <h4 class="text-sm font-bold text-slate-100 break-all">${escapeHtml(f.filename)}</h4>
            <p class="text-xs text-slate-400 mt-2">${escapeHtml(f.ai_summary || '')}</p>
          </div>
          <a href="${API_HOST}/api/files/download?path=${encodeURIComponent(f.filepath)}" target="_blank" class="flex items-center justify-center space-x-2 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 transition">
            <i data-lucide="download" class="w-4 h-4"></i>
            <span>Baixar Arquivo</span>
          </a>
        </div>
      `).join("");

      if (window.lucide) lucide.createIcons();

    } catch (err) {
      document.getElementById("searchResults").innerHTML = `<div class="p-8 text-center text-red-400 font-sans col-span-full">Erro na busca: ${err.message}</div>`;
    }
  }, 300);
}

function formatBytes(bytes, decimals = 1) {
  if (!bytes) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
