#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Port/process inventory for Assistify services (Windows-focused)."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

PORT_OLLAMA = 11434
PORT_PIPER = 5002
PORT_LLM = 8000
PORT_RAG = 7000
PORT_LOGIN = 7001


@dataclass
class ServiceStatus:
    name: str
    port: int
    listening: bool
    pids: List[int]
    process_names: List[str]


def find_pids_on_port_windows(port: int) -> List[int]:
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
    except Exception:
        return []
    pids: set[int] = set()
    for line in out.splitlines():
        if f":{port} " in line or line.rstrip().endswith(f":{port}"):
            parts = line.split()
            if len(parts) >= 5 and parts[-2].upper() == "LISTENING":
                try:
                    pids.add(int(parts[-1]))
                except ValueError:
                    pass
    return sorted(pids)


def _process_name_for_pid(pid: int) -> str:
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            errors="ignore",
        )
        line = out.strip()
        if line and "No tasks" not in line:
            return line.split(",")[0].strip('"')
    except Exception:
        pass
    return "?"


def default_service_specs(
    *,
    llm_port: Optional[int] = None,
    rag_port: Optional[int] = None,
    login_port: Optional[int] = None,
) -> List[Tuple[str, int]]:
    llm = llm_port if llm_port is not None else int(os.environ.get("LLM_SERVER_PORT", PORT_LLM))
    rag = rag_port if rag_port is not None else PORT_RAG
    login = login_port if login_port is not None else PORT_LOGIN
    return [
        ("Ollama", PORT_OLLAMA),
        ("Piper", PORT_PIPER),
        ("LLM", llm),
        ("RAG", rag),
        ("Login", login),
    ]


def scan_services(specs: Iterable[Tuple[str, int]]) -> List[ServiceStatus]:
    rows: List[ServiceStatus] = []
    for name, port in specs:
        pids = find_pids_on_port_windows(port)
        rows.append(
            ServiceStatus(
                name=name,
                port=port,
                listening=bool(pids),
                pids=pids,
                process_names=[_process_name_for_pid(pid) for pid in pids],
            )
        )
    return rows


def print_inventory_table(rows: List[ServiceStatus], *, title: str = "Assistify Process Inventory") -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)
    print(f"{'Service':<10} {'Port':<8} {'Status':<12} {'PID(s)':<14} Process")
    print("-" * 72)
    for row in rows:
        status = "LISTENING" if row.listening else "FREE"
        pid_str = ",".join(str(p) for p in row.pids) if row.pids else "-"
        proc_str = ",".join(row.process_names) if row.process_names else "-"
        print(f"{row.name:<10} {row.port:<8} {status:<12} {pid_str:<14} {proc_str}")
    print("=" * 72)
    print()


def kill_listeners_on_ports(
    ports: Iterable[int],
    *,
    exclude_ollama: bool = True,
) -> List[Tuple[int, List[int]]]:
    killed: List[Tuple[int, List[int]]] = []
    for port in ports:
        if exclude_ollama and port == PORT_OLLAMA:
            continue
        pids = find_pids_on_port_windows(port)
        if not pids:
            continue
        for pid in pids:
            try:
                subprocess.check_call(
                    ["taskkill", "/PID", str(pid), "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        killed.append((port, pids))
    return killed
