#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assistify — recommended one-command project start.

Run from the repo root (or anywhere, using the full path to this file):

    python start_main_servers.py

This is the single entry point to start the full Assistify stack:
  Ollama (11434) -> Piper TTS (5002) -> LLM shim (8010) -> RAG (7000) -> Login (7001)

Under the hood it:
1. Changes the working directory to the repo root (this file's directory).
2. Locates the `assistify_main` conda environment's python.exe.
3. Sets KMP_DUPLICATE_LIB_OK=TRUE.
4. Runs scripts/project_start_server.py with --kill-ports --llm-port 8010.

One-time setup (NOT run by this script) — see README.md section 1:
  conda env create -f environment_main.yml
  python -m backend.load_documents
  python Login_system\\init_users_db.py

Any extra command-line arguments are forwarded to project_start_server.py
(after the defaults), e.g. --no-piper, --no-ollama, --reload.
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
TARGET_SCRIPT = PROJECT_ROOT / "scripts" / "project_start_server.py"
CONDA_ENV_NAME = "assistify_main"
LOGIN_URL = "http://127.0.0.1:7001/login"

# Defaults that mirror the manual command. Extra CLI args are appended after.
DEFAULT_ARGS = ["--kill-ports", "--llm-port", "8010"]


def _candidate_conda_roots() -> list[Path]:
    """Possible base directories that contain a conda installation."""
    roots: list[Path] = []

    user_profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    for name in ("miniconda3", "anaconda3", "Miniconda3", "Anaconda3"):
        roots.append(user_profile / name)

    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        for name in ("miniconda3", "anaconda3", "Miniconda3", "Anaconda3"):
            roots.append(Path(program_data) / name)

    for key in ("CONDA_PREFIX", "CONDA_ROOT", "_CONDA_ROOT"):
        val = os.environ.get(key)
        if val:
            p = Path(val)
            roots.append(p)
            roots.append(p.parent.parent)

    return roots


def find_env_python() -> Path | None:
    """Locate the python.exe (or python) for the assistify_main conda env."""
    is_windows = os.name == "nt"
    python_name = "python.exe" if is_windows else "python"

    for base in _candidate_conda_roots():
        if is_windows:
            candidate = base / "envs" / CONDA_ENV_NAME / python_name
        else:
            candidate = base / "envs" / CONDA_ENV_NAME / "bin" / python_name
        if candidate.exists():
            return candidate

    return None


def print_startup_banner(extra_args: list[str]) -> None:
    """Show what will start and where to open the app."""
    print("====================================")
    print("  Assistify Main Server Launcher")
    print("====================================")
    print("Starting services:")
    print("  Ollama      -> http://127.0.0.1:11434")
    print("  Piper TTS   -> http://127.0.0.1:5002  (skipped if --no-piper)")
    print("  LLM shim    -> http://127.0.0.1:8010")
    print("  RAG server  -> http://127.0.0.1:7000")
    print("  Login UI    -> http://127.0.0.1:7001")
    print()
    print(f"Open when Ready: {LOGIN_URL}")
    print("  Dev login: admin / admin  or  superadmin / superadmin123")
    print()
    print("Wait for [OLLAMA], [LLM], [RAG], [LOGIN] Ready in the log below.")
    print("First RAG boot may take several minutes (Whisper model load).")
    if extra_args:
        print(f"Extra flags: {' '.join(extra_args)}")
    print("Press Ctrl+C to stop all services.")
    print("------------------------------------")


def _conda_env_missing_message() -> str:
    return (
        "[ERROR] Could not find the 'assistify_main' conda environment.\n"
        "        Create it once with:\n"
        "          conda env create -f environment_main.yml\n"
        "        Then run again:\n"
        "          python start_main_servers.py"
    )


def run_via_conda(extra_args: list[str]) -> int:
    """Fallback: use `conda run -n <env>` if a direct python.exe wasn't found."""
    print(f"[LAUNCHER] Falling back to 'conda run -n {CONDA_ENV_NAME}'...")
    print_startup_banner(extra_args)
    cmd = [
        "conda", "run", "--no-capture-output", "-n", CONDA_ENV_NAME,
        "python", str(TARGET_SCRIPT), *DEFAULT_ARGS, *extra_args,
    ]
    try:
        return subprocess.call(cmd, cwd=str(PROJECT_ROOT))
    except FileNotFoundError:
        print(_conda_env_missing_message(), file=sys.stderr)
        return 1


def main() -> int:
    if not TARGET_SCRIPT.exists():
        print(f"[ERROR] Target script not found: {TARGET_SCRIPT}", file=sys.stderr)
        return 1

    os.chdir(PROJECT_ROOT)
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    extra_args = sys.argv[1:]

    env_python = find_env_python()
    if env_python is None:
        return run_via_conda(extra_args)

    print_startup_banner(extra_args)
    print(f"[LAUNCHER] Repo root : {PROJECT_ROOT}")
    print(f"[LAUNCHER] Conda env : {CONDA_ENV_NAME}")
    print(f"[LAUNCHER] Python    : {env_python}")
    print(f"[LAUNCHER] KMP_DUPLICATE_LIB_OK = {os.environ['KMP_DUPLICATE_LIB_OK']}")

    cmd = [str(env_python), str(TARGET_SCRIPT), *DEFAULT_ARGS, *extra_args]
    print(f"[LAUNCHER] Running   : {' '.join(cmd)}")
    print("------------------------------------")

    try:
        return subprocess.call(cmd, cwd=str(PROJECT_ROOT))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
