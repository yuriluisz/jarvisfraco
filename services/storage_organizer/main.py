import os
import sys
import time
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.common.db import get_db
from services.storage_organizer.categorizer import analyze_file_with_ai

INBOX_DIR = BASE_DIR / "storage" / "inbox"
ORGANIZADOS_DIR = BASE_DIR / "storage" / "organizados"

INBOX_DIR.mkdir(parents=True, exist_ok=True)
ORGANIZADOS_DIR.mkdir(parents=True, exist_ok=True)

class InboxHandler(FileSystemEventHandler):
    def on_closed(self, event):
        if not event.is_directory:
            self.process_file(event.src_path)

    def on_created(self, event):
        # Em sistemas operacionais onde on_closed não é disparado
        if not event.is_directory:
            # Aguarda a finalização da cópia do arquivo
            time.sleep(1)
            self.process_file(event.src_path)

    def process_file(self, src_path):
        src = Path(src_path)
        if not src.exists() or src.name.startswith(".") or src.suffix == ".tmp":
            return

        print(f"\n[ORGANIZER] Novo arquivo detectado na inbox: {src.name}")
        
        # Garante que a escrita do arquivo terminou (tamanho estabilizou)
        last_size = -1
        for _ in range(10):
            try:
                curr_size = src.stat().st_size
                if curr_size == last_size and curr_size > 0:
                    break
                last_size = curr_size
                time.sleep(0.5)
            except Exception:
                time.sleep(0.5)

        # Análise com IA
        cat, summary, tags_json = analyze_file_with_ai(src.name)
        file_size = src.stat().st_size
        file_type = src.suffix.replace(".", "").lower() or "outro"

        # Destino organizado
        year_str = time.strftime("%Y")
        dest_folder = ORGANIZADOS_DIR / cat / year_str
        dest_folder.mkdir(parents=True, exist_ok=True)
        dest_path = dest_folder / src.name

        # Evita colisão de nomes
        if dest_path.exists():
            dest_path = dest_folder / f"{src.stem}_{int(time.time())}{src.suffix}"

        try:
            shutil.move(str(src), str(dest_path))
            print(f"[ORGANIZER] Movido com sucesso para: {dest_path}")

            # Indexação no SQLite com FTS5
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO storage_catalog (filename, filepath, file_size, file_type, category, user_description, ai_tags, ai_summary, created_at)
                VALUES (?, ?, ?, ?, ?, '', ?, ?, CURRENT_TIMESTAMP)
            """, (src.name, str(dest_path), file_size, file_type, cat, tags_json, summary))
            conn.commit()
            conn.close()
            print(f"[ORGANIZER] Arquivo indexado no SQLite FTS5 ({cat})!")

        except Exception as e:
            print(f"[ORGANIZER ERROR] Falha ao mover/indexar arquivo: {e}")

def main():
    print(f"[INFO] Watchdog iniciado monitorando inbox em: {INBOX_DIR}")
    event_handler = InboxHandler()
    observer = Observer()
    observer.schedule(event_handler, str(INBOX_DIR), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
