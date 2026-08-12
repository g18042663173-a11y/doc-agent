from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

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


def test_download_resumable_restarts_when_server_ignores_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    full_body = b"A" * 1000

    class FakeResponse:
        def __init__(self, status: int, body: bytes) -> None:
            self.status = status
            self._stream = io.BytesIO(body)

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self, length: int = -1):
            return self._stream.read(length)

    class FakeUrlopen:
        def __init__(self, status: int) -> None:
            self.status = status
            self.requests: list = []

        def __call__(self, request, *, timeout: int):
            self.requests.append((request, timeout))
            if self.status == 206:
                header = request.get_header("Range") or ""
                start = int(header.split("=")[1].split("-")[0]) if "=" in header else 0
                return FakeResponse(206, full_body[start:])
            return FakeResponse(200, full_body)

    # Partial .part exists (e.g. interrupted download), server ignores Range
    # and returns the full body with 200: the file must restart, not duplicate.
    fake = FakeUrlopen(status=200)
    monkeypatch.setattr(package_document_workbench, "urlopen", fake)
    output = tmp_path / "python.zip"
    output.with_suffix(".zip.part").write_bytes(b"partial")

    package_document_workbench._download_resumable("https://example.invalid/python.zip", output, len(full_body))

    assert output.read_bytes() == full_body
    assert not output.with_suffix(".zip.part").exists()

    # Server honoring Range (206) resumes from the existing partial.
    partial = full_body[:600]
    part_path = output.with_suffix(".zip.part")
    part_path.write_bytes(partial)
    fake = FakeUrlopen(status=206)
    monkeypatch.setattr(package_document_workbench, "urlopen", fake)

    package_document_workbench._download_resumable("https://example.invalid/python.zip", output, len(full_body))

    assert output.read_bytes() == full_body
    assert not part_path.exists()


def test_download_resumable_failure_cleans_part_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    class FakeResponse:
        status = 200

        def __init__(self) -> None:
            self._stream = io.BytesIO(b"short")

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self, length: int = -1):
            return self._stream.read(length)

    monkeypatch.setattr(
        package_document_workbench,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    output = tmp_path / "python.zip"

    with pytest.raises(SystemExit):
        package_document_workbench._download_resumable("https://example.invalid/python.zip", output, 1000)

    assert not output.with_suffix(".zip.part").exists()
    assert not output.exists()


def test_portable_backend_bundles_few_shot_samples(tmp_path: Path) -> None:
    package_document_workbench._copy_backend(tmp_path)

    samples = tmp_path / "app" / "samples" / "ir"
    assert samples.is_dir()
    assert len(list(samples.glob("*.json"))) > 0
    # builder.py resolves SAMPLE_DIR via parents[3]; the packaged layout must
    # match so build_prompt does not fail with FileNotFoundError.
    from app.prompting.builder import SAMPLE_DIR

    assert SAMPLE_DIR.resolve().name == "ir"


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
