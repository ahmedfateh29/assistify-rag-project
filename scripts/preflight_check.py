#!/usr/bin/env python3
"""Quick local checks before starting Assistify servers."""
from __future__ import annotations

import socket
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    print(f"Project root: {REPO_ROOT}")
    ok = True

    try:
        from config import WHISPER_MODEL_PATH, ASSETS_DIR
    except Exception as exc:
        print(f"FAIL: cannot import config ({exc})")
        return 1

    whisper = Path(WHISPER_MODEL_PATH)
    print(f"Whisper path: {whisper} -> {'OK' if whisper.exists() else 'MISSING'}")
    if not whisper.exists():
        ok = False

    chroma = REPO_ROOT / "backend" / "chroma_db_v3"
    print(f"Chroma v3: {chroma} -> {'OK' if chroma.is_dir() else 'MISSING'}")
    if chroma.is_dir():
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(chroma))
            names = client.list_collections()
            for name in names:
                col = client.get_collection(name)
                print(f"  collection {name!r}: {col.count()} chunks")
        except Exception as exc:
            print(f"  WARN: chroma read failed ({exc})")
    else:
        ok = False

    assets = Path(ASSETS_DIR)
    pdfs = list(assets.glob("*.pdf")) if assets.is_dir() else []
    print(f"Assets PDFs: {len(pdfs)}")

    for port, label in ((11434, "Ollama"), (7000, "RAG"), (7001, "Login"), (8010, "LLM shim")):
        up = _port_open("127.0.0.1", port)
        print(f"Port {port} ({label}): {'listening' if up else 'down'}")
        if label == "Ollama" and not up:
            ok = False

    print("\nResult:", "READY TO START SERVERS" if ok else "FIX ISSUES ABOVE FIRST")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
