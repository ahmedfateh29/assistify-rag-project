#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assistify main server launcher.

Default on Windows: split-terminal mode (one window per service + coordinator).
Use --single-console for the merged-log launcher (CI / SSH).

Equivalent of the manual PowerShell sequence:

    cd "<repo root>"
    conda activate assistify_main
    $env:KMP_DUPLICATE_LIB_OK = "TRUE"
    python scripts\\project_start_split.py --kill-ports --llm-port 8010
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SPLIT_SCRIPT = PROJECT_ROOT / "scripts" / "project_start_split.py"
SINGLE_SCRIPT = PROJECT_ROOT / "scripts" / "project_start_server.py"
CONDA_ENV_NAME = "assistify_main"

DEFAULT_ARGS = ["--kill-ports", "--llm-port", "8010"]


def _candidate_conda_roots() -> list[Path]:
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


def _resolve_target_script(extra_args: list[str]) -> Path:
    if "--single-console" in extra_args:
        return SINGLE_SCRIPT
    if os.name == "nt":
        return SPLIT_SCRIPT
    return SINGLE_SCRIPT


def print_startup_banner(*, single_console: bool, status_only: bool) -> None:
    print("====================================")
    print("  Assistify Main Server Launcher")
    print("====================================")
    if status_only:
        print("Mode: status inventory only (no services started)")
    elif single_console:
        print("Mode: single-console (merged logs)")
    else:
        print("Mode: multi-terminal (one window per service + this coordinator)")
    print()
    print("Services:")
    print("  Ollama      -> http://127.0.0.1:11434")
    print("  Piper TTS   -> http://127.0.0.1:5002  (skipped if --no-piper)")
    print("  LLM shim    -> http://127.0.0.1:8010")
    print("  RAG server  -> http://127.0.0.1:7000")
    print("  Login UI    -> http://127.0.0.1:7001")
    if not status_only and not single_console:
        print()
        print("Open when Ready: http://127.0.0.1:7001/login")
        print("  Dev login: admin / admin  or  superadmin / superadmin123")
        print()
        print("Coordinator scans ports first, then opens Assistify * windows.")
        print("Close each service window to stop that service.")
        print("First RAG boot may take several minutes (Whisper model load).")
    print("------------------------------------")


def run_via_conda(target: Path, extra_args: list[str]) -> int:
    print(f"[LAUNCHER] Falling back to 'conda run -n {CONDA_ENV_NAME}'...")
    cmd = [
        "conda", "run", "--no-capture-output", "-n", CONDA_ENV_NAME,
        "python", str(target), *DEFAULT_ARGS, *extra_args,
    ]
    try:
        return subprocess.call(cmd, cwd=str(PROJECT_ROOT))
    except FileNotFoundError:
        print(
            "[ERROR] Could not find the 'assistify_main' conda environment or the "
            "'conda' command on PATH.",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    os.chdir(PROJECT_ROOT)
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    extra_args = sys.argv[1:]
    status_only = "--status" in extra_args
    single_console = "--single-console" in extra_args
    target = _resolve_target_script(extra_args)

    if not target.exists():
        print(f"[ERROR] Target script not found: {target}", file=sys.stderr)
        return 1

    print_startup_banner(single_console=single_console, status_only=status_only)

    env_python = find_env_python()
    if env_python is None:
        return run_via_conda(target, extra_args)

    print(f"[LAUNCHER] Repo root : {PROJECT_ROOT}")
    print(f"[LAUNCHER] Conda env : {CONDA_ENV_NAME}")
    print(f"[LAUNCHER] Python    : {env_python}")
    print(f"[LAUNCHER] Script    : {target.name}")
    print(f"[LAUNCHER] KMP_DUPLICATE_LIB_OK = {os.environ['KMP_DUPLICATE_LIB_OK']}")

    cmd = [str(env_python), str(target), *DEFAULT_ARGS, *extra_args]
    print(f"[LAUNCHER] Running   : {' '.join(cmd)}")
    print("------------------------------------")

    try:
        return subprocess.call(cmd, cwd=str(PROJECT_ROOT))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
