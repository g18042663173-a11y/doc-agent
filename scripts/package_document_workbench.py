from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
from urllib.request import Request, urlopen
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.1.0"
PACKAGE_NAME = f"document-workbench-windows-x64-{VERSION}"
DIST = ROOT / "dist"
STAGING_ROOT = DIST / ".dw-stage"
STAGE = STAGING_ROOT / "root"
LEGACY_STAGING_ROOT = DIST / ".document-workbench-staging"
PYTHON_DESCRIPTOR = ROOT / "desktop" / "runtime" / "python-3.12.10.json"
DOTNET_DESCRIPTOR = ROOT / "desktop" / "runtime" / "dotnet-sdk-8.0.423.json"
GRAPHVIZ_DESCRIPTOR = ROOT / "desktop" / "runtime" / "graphviz-15.1.0.json"
TEXT_SUFFIXES = {".json", ".md", ".txt", ".py", ".xaml", ".config", ".xml"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the self-contained Windows native workbench archive.")
    parser.add_argument("--dotnet", type=Path, default=_default_dotnet())
    parser.add_argument("--python-embed", type=Path)
    parser.add_argument("--graphviz-root", type=Path, default=Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Graphviz")
    parser.add_argument("--output-dir", type=Path, default=DIST)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.resolve()
    archive = output_dir / f"{PACKAGE_NAME}.zip"
    digest_file = archive.with_suffix(".zip.sha256")
    if archive.exists() and not args.overwrite:
        raise SystemExit(f"refusing to overwrite existing archive: {archive}")

    descriptors = {
        "python": _read_json(PYTHON_DESCRIPTOR),
        "dotnet_sdk": _read_json(DOTNET_DESCRIPTOR),
        "graphviz": _read_json(GRAPHVIZ_DESCRIPTOR),
    }
    dotnet = args.dotnet.resolve()
    graphviz_root = args.graphviz_root.resolve()
    _verify_dotnet(dotnet, descriptors["dotnet_sdk"])
    python_archive = _resolve_python_archive(args.python_embed, descriptors["python"])
    _verify_graphviz(graphviz_root, descriptors["graphviz"])

    _reset_staging()
    publish_dir = STAGING_ROOT / "dotnet-publish"
    _publish_wpf(dotnet, publish_dir)
    _copy_publish(publish_dir, STAGE)
    _copy_backend(STAGE)
    _install_python_runtime(python_archive, STAGE)
    _copy_graphviz(graphviz_root, STAGE)
    _write_readme(STAGE)
    shutil.copy2(ROOT / "docs" / "THIRD_PARTY_NOTICES_WINDOWS.md", STAGE / "THIRD_PARTY_NOTICES.md")

    manifest = _runtime_manifest(descriptors, python_archive, dotnet, graphviz_root, STAGE)
    manifest_path = STAGE / "runtime-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _assert_clean_package(STAGE)
    _write_file_hashes(STAGE)

    output_dir.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        archive.unlink()
    _zip_stage(STAGE, archive)
    archive_hash = _sha256(archive)
    digest_file.write_text(f"{archive_hash}  {archive.name}\n", encoding="utf-8")
    print(f"archive: {archive}")
    print(f"sha256: {archive_hash}")
    print(f"bytes: {archive.stat().st_size}")
    print(f"files: {sum(1 for path in STAGE.rglob('*') if path.is_file())}")
    return 0


def _default_dotnet() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        managed = Path(local_app_data) / "Codex" / "dotnet-sdk-8.0.423" / "dotnet.exe"
        if managed.is_file():
            return managed
    resolved = shutil.which("dotnet")
    return Path(resolved) if resolved else Path("dotnet.exe")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_dotnet(dotnet: Path, descriptor: dict[str, Any]) -> None:
    if not dotnet.is_file():
        raise SystemExit(f".NET SDK executable is missing: {dotnet}")
    version = _run([str(dotnet), "--version"]).stdout.strip()
    if version != descriptor["version"]:
        raise SystemExit(f"expected .NET SDK {descriptor['version']}, got {version}")


def _resolve_python_archive(explicit: Path | None, descriptor: dict[str, Any]) -> Path:
    candidates = []
    if explicit is not None:
        candidates.append(explicit.resolve())
    temp = os.environ.get("TEMP")
    if temp:
        candidates.append(Path(temp) / Path(descriptor["url"]).name)
    cache = ROOT / "desktop" / "runtime-cache" / Path(descriptor["url"]).name
    candidates.append(cache)
    for candidate in candidates:
        if candidate.is_file() and _sha256(candidate) == descriptor["sha256"]:
            return candidate.resolve()
    cache.parent.mkdir(parents=True, exist_ok=True)
    _download_resumable(descriptor["url"], cache, int(descriptor["bytes"]))
    if _sha256(cache) != descriptor["sha256"]:
        raise SystemExit("downloaded Python embeddable runtime hash does not match the pinned descriptor")
    return cache.resolve()


def _download_resumable(url: str, output: Path, expected_bytes: int) -> None:
    for _attempt in range(8):
        current = output.stat().st_size if output.exists() else 0
        if current == expected_bytes:
            return
        headers = {"User-Agent": "DocumentWorkbenchPackager/2.1.0"}
        if current:
            headers["Range"] = f"bytes={current}-"
        request = Request(url, headers=headers)
        with urlopen(request, timeout=60) as response, output.open("ab" if current else "wb") as stream:
            shutil.copyfileobj(response, stream, length=1024 * 1024)
    if output.stat().st_size != expected_bytes:
        raise SystemExit("Python embeddable runtime download did not complete")


def _verify_graphviz(root: Path, descriptor: dict[str, Any]) -> None:
    dot = root / Path(descriptor["expected_executable"])
    if not dot.is_file():
        raise SystemExit(f"Graphviz runtime is missing: {dot}")
    if _sha256(dot) != descriptor["dot_sha256"]:
        raise SystemExit("Graphviz dot.exe hash does not match the pinned descriptor")
    version = _run([str(dot), "-V"], check=False)
    combined = (version.stdout + version.stderr).strip()
    if descriptor["version"] not in combined:
        raise SystemExit(f"Graphviz version mismatch: {combined}")


def _reset_staging() -> None:
    for candidate in (STAGING_ROOT, LEGACY_STAGING_ROOT):
        resolved = candidate.resolve()
        if resolved.parent != DIST.resolve() or resolved.name not in {
            ".dw-stage",
            ".document-workbench-staging",
        }:
            raise SystemExit("refusing to reset an unexpected staging path")
        if resolved.exists():
            deletion_target = Path(f"\\\\?\\{resolved}") if os.name == "nt" else resolved
            shutil.rmtree(deletion_target, onexc=_rmtree_onexc)
        if resolved.exists():
            raise SystemExit(f"staging directory could not be cleared: {resolved}")
    STAGING_ROOT.mkdir(parents=True)


def _rmtree_onexc(_function: Any, _path: str, exception: BaseException) -> None:
    if isinstance(exception, FileNotFoundError):
        return
    raise exception


def _publish_wpf(dotnet: Path, publish_dir: Path) -> None:
    project = ROOT / "desktop" / "DocumentWorkbench" / "DocumentWorkbench.csproj"
    nuget_config = ROOT / "desktop" / "NuGet.Config"
    environment = dict(os.environ)
    environment["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    _run(
        [
            str(dotnet),
            "restore",
            str(project),
            "--configfile",
            str(nuget_config),
            "--locked-mode",
        ],
        env=environment,
    )
    _run(
        [
            str(dotnet),
            "publish",
            str(project),
            "-c",
            "Release",
            "-r",
            "win-x64",
            "--self-contained",
            "true",
            "--no-restore",
            "-o",
            str(publish_dir),
        ],
        env=environment,
    )


def _copy_publish(publish_dir: Path, stage: Path) -> None:
    stage.mkdir(parents=True, exist_ok=True)
    for path in sorted(publish_dir.iterdir()):
        if path.is_file() and path.suffix.lower() not in {".pdb", ".xml"}:
            shutil.copy2(path, stage / path.name)
    executable = stage / "DocumentWorkbench.exe"
    if not executable.is_file():
        raise SystemExit("single-file WPF publish did not produce DocumentWorkbench.exe")


def _copy_backend(stage: Path) -> None:
    destination = stage / "app" / "backend" / "app"
    shutil.copytree(
        ROOT / "backend" / "app",
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def _install_python_runtime(archive: Path, stage: Path) -> None:
    destination = stage / "runtime" / "python"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(destination)
    pth = destination / "python312._pth"
    pth.write_text(
        "python312.zip\n.\nLib\\site-packages\n..\\..\\app\\backend\nimport site\n",
        encoding="utf-8",
    )
    packages = destination / "Lib" / "site-packages"
    packages.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-index",
            "--find-links",
            str(ROOT / "wheelhouse"),
            "--require-hashes",
            "--no-compile",
            "--target",
            str(packages),
            "-r",
            str(ROOT / "requirements-win312.lock"),
        ]
    )
    for cache in list(packages.rglob("__pycache__")):
        shutil.rmtree(cache)
    for test_directory in sorted(
        (path for path in packages.rglob("*") if path.is_dir() and path.name.lower() in {"test", "tests"}),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        shutil.rmtree(test_directory)


def _copy_graphviz(source: Path, stage: Path) -> None:
    destination = stage / "app" / "tools" / "graphviz"
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("bin", "lib", "share"):
        candidate = source / name
        if candidate.is_dir():
            shutil.copytree(candidate, destination / name)
    for name in ("LICENSE", "LICENSE.txt", "COPYING"):
        candidate = source / name
        if candidate.is_file():
            shutil.copy2(candidate, destination / candidate.name)


def _write_readme(stage: Path) -> None:
    (stage / "README.txt").write_text(
        "文档生成工作台 2.1.0\n"
        "\n"
        "1. 将整个目录解压到当前用户可写位置。\n"
        "2. 双击 DocumentWorkbench.exe；不需要管理员权限或预装 Python/.NET。\n"
        "3. NGA 默认不启用；请在“设置 > NGA”配置、测试并启用。\n"
        "4. Token 保存在当前 Windows 用户凭据管理器，目标名 HuaweiDocumentGenerator/NGA。\n"
        "5. 任务目录位于 %LOCALAPPDATA%\\HuaweiDocumentGenerator\\jobs。\n"
        "\n"
        "正式推广前请完成内网代码签名和干净断网 Windows 10/11 x64 验收。\n",
        encoding="utf-8",
    )


def _runtime_manifest(
    descriptors: dict[str, Any],
    python_archive: Path,
    dotnet: Path,
    graphviz_root: Path,
    stage: Path,
) -> dict[str, Any]:
    return {
        "manifest_version": "1.0",
        "product": "文档生成工作台",
        "product_version": VERSION,
        "target": "Windows 10/11 x64",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("branch", "--show-current"),
            "working_tree_clean": not bool(_git("status", "--short")),
        },
        "runtimes": {
            "dotnet_sdk_used_for_build": {**descriptors["dotnet_sdk"], "executable_sha256": _sha256(dotnet)},
            "python": {**descriptors["python"], "archive_sha256": _sha256(python_archive)},
            "graphviz": {
                **descriptors["graphviz"],
                "dot_sha256": _sha256(graphviz_root / "bin" / "dot.exe"),
            },
        },
        "python_packages": _installed_python_packages(stage / "runtime" / "python" / "Lib" / "site-packages"),
        "security": {
            "api_bind": "127.0.0.1:random",
            "session_header": "X-Workbench-Session",
            "credential_target": "HuaweiDocumentGenerator/NGA",
            "credential_in_archive": False,
        },
    }


def _installed_python_packages(site_packages: Path) -> list[dict[str, str | None]]:
    records = []
    for metadata_path in sorted(site_packages.glob("*.dist-info/METADATA")):
        fields: dict[str, str] = {}
        for line in metadata_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if ": " not in line:
                continue
            key, value = line.split(": ", 1)
            if key in {"Name", "Version", "License-Expression", "License"} and key not in fields:
                fields[key] = value[:300]
        records.append(
            {
                "name": fields.get("Name", metadata_path.parent.name),
                "version": fields.get("Version"),
                "license": fields.get("License-Expression") or fields.get("License") or "see package metadata",
            }
        )
    return records


def _assert_clean_package(stage: Path) -> None:
    forbidden_names = {"settings.json", ".env", ".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
    for path in stage.rglob("*"):
        if path.name in forbidden_names or path.suffix.lower() in {".pyc", ".pyo", ".pdb", ".trx"}:
            raise SystemExit(f"forbidden package content: {path.relative_to(stage)}")
        if path.is_dir() and (path.name == "tests" or path.name.endswith(".Tests")):
            raise SystemExit(f"test directory leaked into package: {path.relative_to(stage)}")
    for path in stage.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 5 * 1024 * 1024:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "top-secret" in text or "provider_secret=" in text:
            raise SystemExit(f"test secret marker leaked into package: {path.relative_to(stage)}")


def _write_file_hashes(stage: Path) -> None:
    lines = []
    for path in sorted(path for path in stage.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt"):
        lines.append(f"{_sha256(path)}  {path.relative_to(stage).as_posix()}")
    (stage / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _zip_stage(stage: Path, archive: Path) -> None:
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(path for path in stage.rglob("*") if path.is_file()):
            bundle.write(path, f"{PACKAGE_NAME}/{path.relative_to(stage).as_posix()}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _run(
    command: list[str],
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
