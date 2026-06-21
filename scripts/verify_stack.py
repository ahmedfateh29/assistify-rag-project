#!/usr/bin/env python3
"""End-to-end health checks for Ollama, Piper, RAG, and Login."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1")
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", "11434"))
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
LLM_PORT = int(os.environ.get("LLM_SERVER_PORT", str(__import__("config").LLM_SERVER_PORT)))


def _get(url: str, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code < 500:
            return True, f"HTTP {r.status_code}"
        return False, f"HTTP {r.status_code}"
    except requests.RequestException as e:
        return False, str(e)


def _post_json(url: str, payload: dict, timeout: float = 10.0) -> tuple[bool, str]:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code == 200:
            return True, "OK"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except requests.RequestException as e:
        return False, str(e)


def run_checks(*, require_piper: bool = True) -> tuple[bool, list[str]]:
    errors: list[str] = []

    ok, detail = _get(f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags")
    print(f"Ollama ({OLLAMA_HOST}:{OLLAMA_PORT}): {'OK' if ok else 'FAIL'} — {detail}")
    if not ok:
        errors.append("Ollama not reachable on port 11434")

    if ok:
        model_ok, model_detail = _post_json(
            f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/show",
            {"model": OLLAMA_MODEL},
        )
        print(f"Ollama model '{OLLAMA_MODEL}': {'OK' if model_ok else 'FAIL'} — {model_detail}")
        if not model_ok:
            errors.append(f"Model '{OLLAMA_MODEL}' not loadable — run: ollama pull {OLLAMA_MODEL}")

    ok, detail = _get(f"http://127.0.0.1:{LLM_PORT}/internal/gpu-status")
    print(f"LLM shim (8010): {'OK' if ok else 'WARN (optional)'} — {detail}")

    if require_piper:
        ok, detail = _get("http://127.0.0.1:5002/health")
        print(f"Piper TTS (5002): {'OK' if ok else 'FAIL'} — {detail}")
        if not ok:
            errors.append("Piper TTS not reachable on port 5002")

    ok, detail = _get("http://127.0.0.1:7000/health", timeout=15.0)
    print(f"RAG (7000): {'OK' if ok else 'FAIL'} — {detail}")
    if not ok:
        errors.append("RAG server not reachable on port 7000")

    ok, detail = _get("http://127.0.0.1:7001/login")
    print(f"Login (7001): {'OK' if ok else 'FAIL'} — {detail}")
    if not ok:
        errors.append("Login server not reachable on port 7001")

    return len(errors) == 0, errors


def main() -> int:
    require_piper = "--no-piper" not in sys.argv
    ok, errors = run_checks(require_piper=require_piper)
    if errors:
        print("\nFAILURES:")
        for e in errors:
            print(f" - {e}")
        return 1
    print("\nStack verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
