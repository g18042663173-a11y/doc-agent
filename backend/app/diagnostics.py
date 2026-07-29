from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from typing import Any


def build_runtime_diagnostics(
    *,
    app_version: str,
    api_version: str,
    deck_ir_version: str,
    generator: str,
    generator_revision: int,
    jobs: dict[str, int],
    runner: dict[str, Any],
    storage_free_bytes: int,
    storage_minimum_free_bytes: int,
) -> dict[str, Any]:
    """Build a path-free diagnostic payload suitable for the desktop client."""

    return {
        "diagnostics_version": "1.0",
        "application": {
            "version": app_version,
            "api_version": api_version,
            "deck_ir_version": deck_ir_version,
        },
        "generator": {
            "name": generator,
            "revision": generator_revision,
        },
        "jobs": jobs,
        "runner": runner,
        "storage": {
            "free_bytes": storage_free_bytes,
            "minimum_free_bytes": storage_minimum_free_bytes,
        },
        "graphviz": graphviz_status(),
    }


def graphviz_status(repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    executable, source = _find_graphviz(root)
    if executable is None:
        return {
            "available": False,
            "source": "missing",
            "version": None,
            "fallback": True,
        }
    return {
        "available": True,
        "source": source,
        "version": _read_graphviz_version(executable),
        "fallback": False,
    }


def configure_graphviz_path(repo_root: Path) -> None:
    executable, _source = _find_graphviz(repo_root.resolve())
    if executable is None:
        return
    directory = str(executable.parent)
    current = os.environ.get("PATH", "")
    entries = current.split(os.pathsep) if current else []
    if directory.casefold() not in {entry.casefold() for entry in entries}:
        os.environ["PATH"] = directory + (os.pathsep + current if current else "")


def _find_graphviz(repo_root: Path) -> tuple[Path | None, str]:
    executable_name = "dot.exe" if os.name == "nt" else "dot"
    bundled = repo_root / "tools" / "graphviz" / "bin" / executable_name
    if bundled.is_file():
        return bundled.resolve(), "bundled"
    resolved = shutil.which("dot.exe") or shutil.which("dot")
    if resolved:
        return Path(resolved).resolve(), "system"
    if os.name == "nt":
        for environment_name in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(environment_name)
            if not base:
                continue
            candidate = Path(base) / "Graphviz" / "bin" / "dot.exe"
            if candidate.is_file():
                return candidate.resolve(), "system"
    return None, "missing"


def _read_graphviz_version(executable: Path) -> str | None:
    try:
        result = subprocess.run(
            [str(executable), "-V"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = (result.stdout or result.stderr).strip()
    return value[:200] or None
