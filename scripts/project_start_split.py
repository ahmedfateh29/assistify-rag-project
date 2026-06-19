#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assistify split-terminal launcher (Windows).

Phase 1: Scan and print process inventory.
Phase 2: Optionally free occupied ports (--kill-ports).
Phase 3: Open one cmd window per service, sequentially with readiness gating.
Phase 4: Coordinator polls health after each spawn.

Non-Windows: falls back to scripts/project_start_server.py (single console).
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.service_inventory import (  # noqa: E402
    PORT_OLLAMA,
    PORT_PIPER,
    default_service_specs,
    kill_listeners_on_ports,
    print_inventory_table,
    scan_services,
)
from scripts.project_start_server import (  # noqa: E402
    IS_WINDOWS,
    REPO_ROOT as _REPO,
    SERVICES,
    _host_for_check,
    _piper_voice_env,
    ensure_cwd_and_path,
    http_check,
    parse_args,
    wait_for_port,
)
from scripts.launch_windows.write_launch_scripts import (  # noqa: E402
    LAUNCH_DIR,
    resolve_ollama_exe,
    write_service_bats,
)

assert REPO_ROOT == _REPO

SPAWN_SETTLE_SEC = 1.5


def _resolve_python_exe() -> str:
    user_profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    for base_name in ("miniconda3", "anaconda3", "Miniconda3", "Anaconda3"):
        candidate = user_profile / base_name / "envs" / "assistify_main" / "python.exe"
        if candidate.exists():
            return str(candidate)
    return sys.executable


def spawn_bat_window(title: str, bat_path: Path) -> None:
    """Open a new cmd window that runs a service batch file.

    Avoid Windows ``START`` title parsing (``Assistify Piper`` runs ``Piper`` as a
    command). ``CREATE_NEW_CONSOLE`` opens a visible window; each bat sets ``title``.
    """
    bat = str(bat_path.resolve())
    subprocess.Popen(
        ["cmd", "/k", bat],
        cwd=str(REPO_ROOT),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    print(f"[LAUNCHER] Opened window: {title}")


def build_rag_env(args) -> dict:
    rag_env = {
        "WHISPER_DEVICE": "cpu",
        "WHISPER_COMPUTE_TYPE": "int8",
        "RAG_USE_GPU": "1",
    }
    if args.use_whisper:
        rag_env["USE_WHISPER"] = "1"
    if args.whisper_model:
        rag_env["WHISPER_MODEL"] = args.whisper_model
    if args.whisper_chunk_ms:
        rag_env["WHISPER_CHUNK_MS"] = str(args.whisper_chunk_ms)
    return rag_env


def generate_launch_bats(args, python_exe: str) -> dict[str, Path]:
    return write_service_bats(
        REPO_ROOT,
        python_exe,
        llm=SERVICES[0],
        rag=SERVICES[1],
        login=SERVICES[2],
        rag_env=build_rag_env(args),
        piper_env=_piper_voice_env() or {},
        reload_flag=args.reload,
    )


def apply_cli_overrides(args) -> None:
    if args.llm_host is not None:
        SERVICES[0]["host"] = args.llm_host
    if args.rag_host is not None:
        SERVICES[1]["host"] = args.rag_host
    if args.login_host is not None:
        SERVICES[2]["host"] = args.login_host
    if args.llm_port is not None:
        SERVICES[0]["port"] = args.llm_port
    if args.rag_port is not None:
        SERVICES[1]["port"] = args.rag_port
    if args.login_port is not None:
        SERVICES[2]["port"] = args.login_port


async def wait_service_ready(name: str, host: str, port: int, ready_path: str, quick: bool) -> bool:
    if quick:
        timeout = 30.0
    elif name in ("LLM", "OLLAMA"):
        timeout = 120.0
    elif name == "RAG":
        timeout = 600.0
    else:
        timeout = 60.0

    check_host = _host_for_check(host)
    if not await wait_for_port(check_host, port, timeout=timeout):
        print(f"[{name}] Port {port} did not open in time.")
        return False

    if ready_path:
        url = f"http://{check_host}:{port}{ready_path}"
        for _ in range(30):
            if await http_check(url):
                print(f"[{name}] Ready on http://{host}:{port}")
                return True
            await asyncio.sleep(1.0)
        print(f"[{name}] Warning: health check {ready_path} did not respond; port is open.")
        return True

    print(f"[{name}] Ready on http://{host}:{port}")
    return True


def report_service_failure(
    name: str,
    window_title: str,
    specs,
    *,
    extra_hint: Optional[str] = None,
) -> None:
    print()
    print(f'[{name}] Startup failed — check the "{window_title}" window for errors above.')
    if extra_hint:
        print(f"[{name}] Hint: {extra_hint}")
    print_inventory_table(
        scan_services(specs),
        title=f"Assistify Process Inventory (after {name} failure)",
    )
    print()


async def start_service_sequential(
    name: str,
    bat_path: Path,
    window_title: str,
    host: str,
    port: int,
    ready_path: str,
    args,
    status_by_name: dict,
    specs,
    *,
    failure_hint: Optional[str] = None,
) -> bool:
    row = status_by_name.get(name)
    if row and row.listening:
        print(f"[{name}] Already running on port {row.port} — skipping new window")
        return True

    print(f"[COORDINATOR] Starting {name} in a new window...")
    spawn_bat_window(window_title, bat_path)
    await asyncio.sleep(SPAWN_SETTLE_SEC)

    ok = await wait_service_ready(name.upper(), host, port, ready_path, args.quick)
    if not ok:
        report_service_failure(name.upper(), window_title, specs, extra_hint=failure_hint)
    return ok


async def run_split_launcher(args) -> int:
    ensure_cwd_and_path()
    apply_cli_overrides(args)

    python_exe = _resolve_python_exe()
    print(f"[COORDINATOR] Repo root : {REPO_ROOT}")
    print(f"[COORDINATOR] Python    : {python_exe}")
    print(f"[COORDINATOR] Launchers : {LAUNCH_DIR}")

    specs = default_service_specs(
        llm_port=SERVICES[0]["port"],
        rag_port=SERVICES[1]["port"],
        login_port=SERVICES[2]["port"],
    )
    inventory = scan_services(specs)
    print_inventory_table(inventory, title="Assistify Process Inventory (before start)")

    if args.kill_ports:
        ports = [SERVICES[0]["port"], SERVICES[1]["port"], SERVICES[2]["port"]]
        if not args.no_piper:
            ports.append(PORT_PIPER)
        killed = kill_listeners_on_ports(ports, exclude_ollama=True)
        for port, pids in killed:
            print(f"[COORDINATOR] Freed port {port} (PIDs: {pids})")
        inventory = scan_services(specs)
        print_inventory_table(inventory, title="Assistify Process Inventory (after --kill-ports)")

    status_by_name = {row.name: row for row in inventory}
    bats = generate_launch_bats(args, python_exe)

    all_ok = True
    failures: list[str] = []

    if not args.no_ollama:
        if status_by_name["Ollama"].listening:
            print(f"[OLLAMA] Already running on 127.0.0.1:{PORT_OLLAMA}")
        else:
            ollama_exe = resolve_ollama_exe()
            print(f"[COORDINATOR] Ollama binary: {ollama_exe}")
            ok = await start_service_sequential(
                "Ollama",
                bats["Ollama"],
                "Assistify Ollama",
                "127.0.0.1",
                PORT_OLLAMA,
                "",
                args,
                status_by_name,
                specs,
                failure_hint="Start the Ollama tray app, install the CLI, or re-run with --no-ollama",
            )
            all_ok = all_ok and ok
            if not ok:
                failures.append("Ollama")
    else:
        print("[SKIPPED] Ollama (--no-ollama)")

    startup_plan = [
        ("Piper", "Piper", "127.0.0.1", PORT_PIPER, "/health", args.no_piper, None),
        (
            "LLM",
            "LLM",
            SERVICES[0]["host"],
            SERVICES[0]["port"],
            SERVICES[0]["ready_path"],
            args.no_llm,
            None,
        ),
        (
            "RAG",
            "RAG",
            SERVICES[1]["host"],
            SERVICES[1]["port"],
            SERVICES[1]["ready_path"],
            args.no_rag,
            None,
        ),
        (
            "Login",
            "Login",
            SERVICES[2]["host"],
            SERVICES[2]["port"],
            SERVICES[2]["ready_path"],
            args.no_login,
            None,
        ),
    ]

    print()
    print("[COORDINATOR] Starting services sequentially (spawn → wait → next)...")
    print("-" * 72)

    for key, display, host, port, ready_path, skipped, hint in startup_plan:
        if skipped:
            print(f"[SKIPPED] {display}")
            continue
        ok = await start_service_sequential(
            key,
            bats[key],
            f"Assistify {display}",
            host,
            port,
            ready_path,
            args,
            status_by_name,
            specs,
            failure_hint=hint,
        )
        all_ok = all_ok and ok
        if not ok:
            failures.append(display)

    print()
    print("=" * 72)
    if all_ok:
        print("  ALL SERVICES READY")
    else:
        print("  STARTUP COMPLETED WITH WARNINGS")
        print(f"  Failed or timed out: {', '.join(failures)}")
        print("  Check the matching Assistify * windows for error output.")
    print("=" * 72)
    print(f"  Open: http://127.0.0.1:{SERVICES[2]['port']}/login")
    print("  Dev login: admin / admin  or  superadmin / superadmin123")
    print()
    print("  Each service runs in its own window titled 'Assistify ...'.")
    print("  Close those windows to stop individual services.")
    print("  Press Ctrl+C here to exit the coordinator (service windows stay open).")
    print("=" * 72)

    print_inventory_table(
        scan_services(specs),
        title="Assistify Process Inventory (final)",
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\n[COORDINATOR] Exiting. Service windows are still running — close them manually.")
        return 0

    return 0 if all_ok else 1


def run_status_only(args) -> int:
    ensure_cwd_and_path()
    apply_cli_overrides(args)
    specs = default_service_specs(
        llm_port=SERVICES[0]["port"],
        rag_port=SERVICES[1]["port"],
        login_port=SERVICES[2]["port"],
    )
    print_inventory_table(scan_services(specs))
    return 0


def main() -> int:
    if not IS_WINDOWS:
        print("[LAUNCHER] Split-terminal mode is Windows-only; using single-console launcher.")
        script = REPO_ROOT / "scripts" / "project_start_server.py"
        argv = [a for a in sys.argv[1:] if a != "--status"]
        return subprocess.call([sys.executable, str(script), *argv], cwd=str(REPO_ROOT))

    argv = sys.argv[1:]
    status_only = False
    if "--status" in argv:
        status_only = True
        argv = [a for a in argv if a != "--status"]
    sys.argv = [sys.argv[0], *argv]

    args = parse_args()
    if status_only:
        return run_status_only(args)
    return asyncio.run(run_split_launcher(args))


if __name__ == "__main__":
    raise SystemExit(main())
