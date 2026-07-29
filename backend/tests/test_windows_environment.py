from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.web_api import main as web_api_main
from scripts.package_windows_dev import _collect_package_files


ROOT = Path(__file__).resolve().parents[2]


def test_environment_report_records_python_utf8_and_graphviz_fallback_state(tmp_path: Path) -> None:
    output = tmp_path / "environment_report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "environment_report.py"),
            "--repo-root",
            str(ROOT),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["report_version"] == "1.0"
    assert report["python"]["version"].startswith("3.12")
    assert report["graphviz"]["source"] in {"bundled", "system", "missing"}
    assert report["graphviz"]["fallback"] is (not report["graphviz"]["available"])
    if report["graphviz"]["available"]:
        assert len(report["graphviz"]["sha256"]) == 64
        assert "graphviz version" in report["graphviz"]["version"]


def test_workbench_scripts_use_repository_python_local_binding_and_owned_pid() -> None:
    start = (ROOT / "start_workbench.ps1").read_text(encoding="utf-8")
    stop = (ROOT / "stop_workbench.ps1").read_text(encoding="utf-8")

    assert '.venv\\Scripts\\python.exe' in start
    assert '127.0.0.1' in start
    assert '/api/health' in start
    assert '-WindowStyle Hidden' in start
    assert 'workbench.pid' in start and 'workbench.pid' in stop
    assert 'ExecutablePath -ne $Python' in stop
    assert 'app\\.web_api' in stop


def test_production_entrypoint_rejects_nonlocal_binding() -> None:
    with pytest.raises(SystemExit) as captured:
        web_api_main(["--host", "0.0.0.0", "--port", "5056"])
    assert captured.value.code == 2


def test_delivery_archive_excludes_stale_root_manifest_before_writing_generated_manifest() -> None:
    files, _skipped = _collect_package_files(include_git=False, include_wheelhouse=False)
    relative_paths = [relative.as_posix() for _path, relative in files]

    assert "MIGRATION_PACKAGE_MANIFEST.json" not in relative_paths
