import os
import sqlite3
from pathlib import Path

# Determina o caminho padrão da raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "server.db"

def get_db_path(custom_path=None):
    if custom_path:
        return Path(custom_path)
    env_path = os.getenv("JARVIS_DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH

def get_db(custom_path=None):
    db_file = get_db_path(custom_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db(custom_path=None):
    """Inicializa todas as tabelas, índices e a busca em texto pleno (FTS5)."""
    conn = get_db(custom_path)
    cur = conn.cursor()

    # 1. Configurações Dinâmicas do Sistema
    cur.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Catálogo de Arquivos e Metadados
    cur.execute("""
        CREATE TABLE IF NOT EXISTS storage_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL UNIQUE,
            file_size INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            category TEXT NOT NULL,
            user_description TEXT,
            ai_tags TEXT,
            ai_summary TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 3. Busca em Texto Pleno (FTS5)
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS storage_catalog_fts USING fts5(
            filename,
            category,
            user_description,
            ai_tags,
            ai_summary,
            content='storage_catalog',
            content_rowid='id'
        );
    """)

    # 4. Logs de Eventos do Sentinela
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sentry_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            details TEXT,
            snapshot_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 5. Diário de Voz e Interações
    cur.execute("""
        CREATE TABLE IF NOT EXISTS voice_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            transcription TEXT,
            intent_detected TEXT,
            response_text TEXT,
            latency_ms INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 6. Histórico de Telemetria
    cur.execute("""
        CREATE TABLE IF NOT EXISTS system_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpu_usage_pct REAL,
            ram_usage_mb REAL,
            disk_free_gb REAL,
            recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Valores padrão de configuração inicial
    defaults = [
        ("assistant_name", "Jarvis", "Nome falado pelo assistente"),
        ("wake_words", "jarvis,computador", "Palavras de ativação separadas por vírgula"),
        ("sentry_state", "DISARMED", "Estado atual da sentinela: ARMED ou DISARMED"),
        ("mic_threshold", "200", "Sensibilidade mínima em RMS do microfone"),
        ("tts_voice", "pt-BR-AntonioNeural", "Voz neural usada no sintetizador"),
        ("system_prompt", "Você é o Jarvis, um assistente inteligente e altamente técnico para um Home Server. Responda de forma direta, clara e concisa.", "Prompt de personalidade da IA")
    ]

    for key, val, desc in defaults:
        cur.execute("""
            INSERT OR IGNORE INTO system_config (key, value, description)
            VALUES (?, ?, ?);
        """, (key, val, desc))

    conn.commit()
    conn.close()
    print(f"[DB] Banco de dados inicializado com sucesso em: {get_db_path(custom_path)}")

def get_config(key, default=None, custom_path=None):
    try:
        conn = get_db(custom_path)
        cur = conn.cursor()
        cur.execute("SELECT value FROM system_config WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return row["value"] if row else default
    except Exception:
        return default

def set_config(key, value, description=None, custom_path=None):
    conn = get_db(custom_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO system_config (key, value, description, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value=excluded.value,
            description=COALESCE(excluded.description, system_config.description),
            updated_at=CURRENT_TIMESTAMP;
    """, (key, str(value), description))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
