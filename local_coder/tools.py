from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ToolError(RuntimeError):
    pass


@dataclass
class WriteRecord:
    path: str
    bytes_written: int


def _safe_resolve(path: str) -> Path:
    p = Path(path).expanduser()
    # Allow relative paths, resolve against cwd.
    try:
        return p.resolve()
    except FileNotFoundError:
        # resolve() can fail if parts don't exist on some platforms
        return (Path.cwd() / p).resolve()


def read_file(path: str, *, max_bytes: int = 250_000) -> dict[str, Any]:
    p = _safe_resolve(path)
    if not p.exists():
        raise ToolError(f"File not found: {p}")
    if not p.is_file():
        raise ToolError(f"Not a file: {p}")
    data = p.read_bytes()
    truncated = False
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated = True
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    return {"path": str(p), "content": text, "truncated": truncated, "bytes": len(data)}


def write_file(path: str, content: str) -> dict[str, Any]:
    p = _safe_resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = content.encode("utf-8")
    p.write_bytes(raw)
    return {"path": str(p), "bytes_written": len(raw)}


def list_directory(path: str = ".") -> dict[str, Any]:
    p = _safe_resolve(path)
    if not p.exists():
        raise ToolError(f"Directory not found: {p}")
    if not p.is_dir():
        raise ToolError(f"Not a directory: {p}")
    entries: list[dict[str, Any]] = []
    for child in sorted(p.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())):
        try:
            st = child.stat()
            size = st.st_size
        except OSError:
            size = None
        entries.append(
            {
                "name": child.name,
                "path": str(child),
                "type": "dir" if child.is_dir() else "file",
                "size": size,
            }
        )
    return {"path": str(p), "entries": entries}


def run_terminal_command(command: str, *, cwd: str | None = None, timeout_s: int = 120) -> dict[str, Any]:
    if not isinstance(command, str) or not command.strip():
        raise ToolError("Command must be a non-empty string.")
    run_cwd = _safe_resolve(cwd).as_posix() if cwd else None
    completed = subprocess.run(
        command,
        shell=True,
        cwd=run_cwd,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=timeout_s,
    )
    return {
        "command": command,
        "cwd": run_cwd or os.getcwd(),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }

