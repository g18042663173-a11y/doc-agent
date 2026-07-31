from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

from app.version import APP_VERSION
from scripts import package_document_workbench


ROOT = Path(__file__).resolve().parents[2]


def test_root_version_is_the_python_product_version() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
    assert APP_VERSION == version
    assert package_document_workbench.VERSION == version


def test_portable_backend_carries_the_canonical_version(tmp_path: Path) -> None:
    package_document_workbench._copy_backend(tmp_path)

    assert (tmp_path / "app" / "VERSION").read_text(encoding="utf-8").strip() == APP_VERSION
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(tmp_path / "app" / "backend")
    result = subprocess.run(
        [sys.executable, "-c", "from app.version import APP_VERSION; print(APP_VERSION)"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == APP_VERSION


def test_wpf_uses_build_version_instead_of_hardcoded_display_versions() -> None:
    project = (ROOT / "desktop" / "DocumentWorkbench" / "DocumentWorkbench.csproj").read_text(encoding="utf-8")
    app_info = (ROOT / "desktop" / "DocumentWorkbench" / "AppInfo.cs").read_text(encoding="utf-8")
    xaml = (ROOT / "desktop" / "DocumentWorkbench" / "MainWindow.xaml").read_text(encoding="utf-8")
    backend_host = (ROOT / "desktop" / "DocumentWorkbench" / "BackendProcessHost.cs").read_text(encoding="utf-8")

    assert "VERSION" in project
    assert "ReadAllText" in project
    assert "Assembly.GetName().Version" in app_info
    assert "{x:Static local:AppInfo.ProductVersionLabel}" in xaml
    assert "{x:Static local:AppInfo.PlatformVersionLabel}" in xaml
    assert "AppInfo.Version" in backend_host
    assert APP_VERSION not in xaml
    assert f"DocumentWorkbench/{APP_VERSION}" not in backend_host
