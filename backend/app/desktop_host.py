from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
from threading import Thread
import time
from typing import Any

from waitress import create_server

from app.diagnostics import configure_graphviz_path
from app.web_api import APP_VERSION, create_api_app


MAX_BOOTSTRAP_BYTES = 16 * 1024


@dataclass(frozen=True)
class DesktopBootstrap:
    session_token: str
    state_path: Path
    jobs_path: Path
    parent_pid: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the protected local desktop API host.")
    parser.add_argument("--bootstrap", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bootstrap = load_bootstrap(args.bootstrap)
    repo_root = Path(__file__).resolve().parents[2]
    configure_graphviz_path(repo_root)
    bootstrap.jobs_path.mkdir(parents=True, exist_ok=True)

    app = create_api_app(
        work_dir=bootstrap.jobs_path,
        session_token=bootstrap.session_token,
    )
    server = create_server(app, host="127.0.0.1", port=0, threads=4)
    port = int(server.effective_port)
    _write_state(
        bootstrap.state_path,
        {
            "state_version": "1.0",
            "pid": os.getpid(),
            "parent_pid": bootstrap.parent_pid,
            "port": port,
            "app_version": APP_VERSION,
            "started_at_unix": int(time.time()),
        },
    )
    Thread(
        target=_stop_when_parent_exits,
        args=(bootstrap.parent_pid, server),
        name="desktop-parent-watchdog",
        daemon=True,
    ).start()
    try:
        server.run()
    finally:
        _remove_owned_state(bootstrap.state_path, os.getpid())
    return 0


def load_bootstrap(path: Path) -> DesktopBootstrap:
    resolved = path.resolve(strict=True)
    _require_runtime_path(resolved)
    if not resolved.name.startswith("bootstrap-") or resolved.suffix.lower() != ".json":
        raise ValueError("desktop bootstrap filename is invalid")
    if resolved.stat().st_size > MAX_BOOTSTRAP_BYTES:
        raise ValueError("desktop bootstrap file is too large")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    finally:
        resolved.unlink(missing_ok=True)
    if not isinstance(payload, dict) or set(payload) != {
        "bootstrap_version",
        "session_token",
        "state_path",
        "jobs_path",
        "parent_pid",
    }:
        raise ValueError("desktop bootstrap shape is invalid")
    if payload["bootstrap_version"] != "1.0":
        raise ValueError("desktop bootstrap version is unsupported")
    token = payload["session_token"]
    if not isinstance(token, str) or len(token) < 32 or len(token) > 256:
        raise ValueError("desktop session token is invalid")
    parent_pid = payload["parent_pid"]
    if not isinstance(parent_pid, int) or parent_pid <= 0:
        raise ValueError("desktop parent PID is invalid")
    state_path = Path(str(payload["state_path"])).resolve()
    jobs_path = Path(str(payload["jobs_path"])).resolve()
    _require_runtime_path(state_path)
    _require_app_data_path(jobs_path)
    if not state_path.name.startswith("backend-state-") or state_path.suffix.lower() != ".json":
        raise ValueError("desktop state filename is invalid")
    if jobs_path != (_local_app_root() / "jobs").resolve():
        raise ValueError("desktop jobs path is invalid")
    return DesktopBootstrap(token, state_path, jobs_path, parent_pid)


def _local_app_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise ValueError("LOCALAPPDATA is not configured")
    return (Path(local_app_data) / "HuaweiDocumentGenerator").resolve()


def _require_runtime_path(path: Path) -> None:
    runtime = (_local_app_root() / "runtime").resolve()
    if not path.is_relative_to(runtime):
        raise ValueError("desktop runtime path is outside the application directory")


def _require_app_data_path(path: Path) -> None:
    if not path.is_relative_to(_local_app_root()):
        raise ValueError("desktop data path is outside the application directory")


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _stop_when_parent_exits(parent_pid: int, server: Any) -> None:
    while _process_exists(parent_pid):
        time.sleep(1)
    server.close()


def _process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _remove_owned_state(path: Path, pid: int) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if payload.get("pid") == pid:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
