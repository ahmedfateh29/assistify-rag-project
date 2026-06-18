#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assistify main server launcher.

Equivalent of the manual PowerShell sequence:

    cd "<repo root>"
    conda activate assistify_main
    $env:KMP_DUPLICATE_LIB_OK = "TRUE"
    python scripts\\project_start_server.py --kill-ports --llm-port 8010

This script:
1. Changes the working directory to the repo root (this file's directory).
2. Locates the `assistify_main` conda environment's python.exe.
3. Sets KMP_DUPLICATE_LIB_OK=TRUE.
4. Runs scripts/project_start_server.py with --kill-ports --llm-port 8010,
   streaming its output to this console.

Any extra command line arguments passed to this script are forwarded to
project_start_server.py (after the defaults), so you can add flags like
--no-llm, --reload, etc.
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
TARGET_SCRIPT = PROJECT_ROOT / "scripts" / "project_start_server.py"
CONDA_ENV_NAME = "assistify_main"

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

    # If conda is already active / installed, honor its base.
    for key in ("CONDA_PREFIX", "CONDA_ROOT", "_CONDA_ROOT"):
        val = os.environ.get(key)
        if val:
            p = Path(val)
            # CONDA_PREFIX may point at an env, so also include its parent's parent base.
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


def run_via_conda(extra_args: list[str]) -> int:
    """Fallback: use `conda run -n <env>` if a direct python.exe wasn't found."""
    print(f"[LAUNCHER] Falling back to 'conda run -n {CONDA_ENV_NAME}'...")
    cmd = [
        "conda", "run", "--no-capture-output", "-n", CONDA_ENV_NAME,
        "python", str(TARGET_SCRIPT), *DEFAULT_ARGS, *extra_args,
    ]
    try:
        return subprocess.call(cmd, cwd=str(PROJECT_ROOT))
    except FileNotFoundError:
        print(
            "[ERROR] Could not find the 'assistify_main' conda environment or the "
            "'conda' command on PATH.\n"
            "        Make sure Miniconda/Anaconda is installed and the "
            "'assistify_main' environment exists.",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    if not TARGET_SCRIPT.exists():
        print(f"[ERROR] Target script not found: {TARGET_SCRIPT}", file=sys.stderr)
        return 1

    # cd "<repo root>"
    os.chdir(PROJECT_ROOT)

    # $env:KMP_DUPLICATE_LIB_OK = "TRUE"
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    # Forward any extra args the user passes to this launcher.
    extra_args = sys.argv[1:]

    env_python = find_env_python()
    if env_python is None:
        # Try conda run as a fallback before giving up.
        return run_via_conda(extra_args)

    print("====================================")
    print("  Assistify Main Server Launcher")
    print("====================================")
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
