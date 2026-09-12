from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import app.desktop_host as desktop_host


def _bootstrap_payload(root: Path) -> dict[str, object]:
    return {
        "bootstrap_version": "1.0",
        "session_token": "s" * 48,
        "state_path": str(root / "runtime" / "backend-state-test.json"),
        "jobs_path": str(root / "jobs"),
        "parent_pid": os.getpid(),
    }


def test_load_bootstrap_accepts_only_local_app_directory_and_deletes_secret_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app_root = tmp_path / "HuaweiDocumentGenerator"
    bootstrap_path = app_root / "runtime" / "bootstrap-test.json"
    bootstrap_path.parent.mkdir(parents=True)
    bootstrap_path.write_text(json.dumps(_bootstrap_payload(app_root)), encoding="utf-8")

    loaded = desktop_host.load_bootstrap(bootstrap_path)

    assert loaded.session_token == "s" * 48
    assert loaded.jobs_path == (app_root / "jobs").resolve()
    assert not bootstrap_path.exists()


def test_load_bootstrap_rejects_paths_outside_local_app_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    runtime = tmp_path / "local" / "HuaweiDocumentGenerator" / "runtime"
    runtime.mkdir(parents=True)
    bootstrap_path = runtime / "bootstrap-test.json"
    payload = _bootstrap_payload(tmp_path / "outside")
    bootstrap_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="outside"):
        desktop_host.load_bootstrap(bootstrap_path)

    assert not bootstrap_path.exists()


def test_desktop_host_binds_loopback_random_port_and_writes_path_free_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app_root = tmp_path / "HuaweiDocumentGenerator"
    bootstrap_path = app_root / "runtime" / "bootstrap-test.json"
    bootstrap_path.parent.mkdir(parents=True)
    bootstrap_path.write_text(json.dumps(_bootstrap_payload(app_root)), encoding="utf-8")
    calls: dict[str, object] = {}

    class FakeServer:
        effective_port = 54321

        def run(self) -> None:
            calls["ran"] = True

        def close(self) -> None:
            calls["closed"] = True

    def fake_create_server(_app, **kwargs):
        calls["server"] = kwargs
        return FakeServer()

    monkeypatch.setattr(desktop_host, "create_server", fake_create_server)
    monkeypatch.setattr(desktop_host, "_remove_owned_state", lambda _path, _pid: None)

    assert desktop_host.main(["--bootstrap", str(bootstrap_path)]) == 0

    assert calls["server"] == {"host": "127.0.0.1", "port": 0, "threads": 4}
    assert calls["ran"] is True
    state = json.loads((app_root / "runtime" / "backend-state-test.json").read_text(encoding="utf-8"))
    assert state["port"] == 54321
    assert state["parent_pid"] == os.getpid()
    assert "session" not in json.dumps(state).lower()


@pytest.mark.skipif(os.name != "nt", reason="Windows process handle semantics")
def test_process_probe_rejects_terminated_process_with_an_open_handle() -> None:
    process = subprocess.Popen([sys.executable, "-c", "pass"], encoding="utf-8")
    try:
        process.wait(timeout=10)

        assert desktop_host._process_exists(process.pid) is False
        assert desktop_host._process_exists(os.getpid()) is True
    finally:
        process._handle.Close()
