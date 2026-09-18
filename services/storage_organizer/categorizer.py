import os
import json
import subprocess
from pathlib import Path

EXT_MAP = {
    "Documentos": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".odt"],
    "Fotos": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tiff"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"],
    "Musicas": [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"],
    "ISOs": [".iso", ".img", ".vmdk", ".vhd", ".qcow2"],
    "Compactados": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"]
}

def detect_category_by_extension(filename):
    ext = Path(filename).suffix.lower()
    for cat, exts in EXT_MAP.items():
        if ext in exts:
            return cat
    return "Outros"

def analyze_file_with_ai(filename, agy_path="agy"):
    """Gera resumo e tags inteligentes via Antigravity CLI / Gemini."""
    prompt = (
        f"Analise o nome e formato deste arquivo: \"{filename}\". "
        "Retorne APENAS um JSON no formato: "
        "{\"category\": \"Documentos|Fotos|Videos|Musicas|ISOs|Outros\", \"summary\": \"breve resumo de 1 frase\", \"tags\": [\"tag1\", \"tag2\"]}"
    )

    try:
        cmd = [agy_path, "-p", prompt, "--dangerously-skip-permissions"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if res.returncode == 0 and res.stdout.strip():
            raw = res.stdout.strip()
            # Tenta limpar blocos markdown ```json
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            data = json.loads(raw)
            return data.get("category"), data.get("summary"), json.dumps(data.get("tags", []))
    except Exception:
        pass

    # Fallback se IA não estiver disponível
    cat = detect_category_by_extension(filename)
    return cat, f"Arquivo {cat} arquivado automaticamente.", "[]"
