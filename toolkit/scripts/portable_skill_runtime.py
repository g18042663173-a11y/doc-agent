"""Build and verify independent Windows runtimes for the two Agent skills.

Only the build machine uses pip. Delivered skills never install dependencies or
consult a repository, another package, PYTHONPATH, or the system Python.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "SKILL_PACKAGE_MANIFEST.json"
LOCKS = {
    "huawei-doc-workflow": ROOT / "requirements-generation-win312.lock",
    "rhetoric-deck-workflow": ROOT / "requirements-imitation-win312.lock",
}
ENTRIES = {
    "huawei-doc-workflow": "scripts/workflow.py",
    "rhetoric-deck-workflow": "bin/rdw.py",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def records(root: Path) -> list[dict]:
    return [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(root.rglob("*")) if path.is_file() and path.name != MANIFEST
    ]


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def isolated_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in list(environment):
        if key.upper().startswith("PYTHON") or key.upper() in {"VIRTUAL_ENV", "CONDA_PREFIX"}:
            environment.pop(key)
    windows = Path(os.environ.get("SystemRoot", "C:/Windows"))
    environment["PATH"] = os.pathsep.join(str(windows / part) for part in ("System32", "System32/WindowsPowerShell/v1.0"))
    environment["SKILL_NETWORK_DISABLED"] = "1"
    environment["PIP_NO_INDEX"] = "1"
    return environment


def _run(command: list[str], *, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(command, cwd=cwd or ROOT, env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=300)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {command[0]}\n{result.stderr or result.stdout}")
    return result


def prepare_runtime(skill_name: str) -> Path:
    """Return a content-addressed, verified runtime cache; never mutate a skill source tree."""
    if sys.version_info[:2] != (3, 12) or sys.platform != "win32":
        raise RuntimeError("Portable Windows builds require CPython 3.12 on Windows x64.")
    lock = LOCKS[skill_name]
    descriptor = json.loads((ROOT / "desktop/runtime/python-3.12.10.json").read_text(encoding="utf-8"))
    archive = ROOT / "desktop/runtime-cache" / Path(descriptor["url"]).name
    if not archive.is_file() or sha256(archive) != descriptor["sha256"]:
        raise RuntimeError("Pinned Python embed archive is missing or corrupt; populate desktop/runtime-cache first.")
    key = hashlib.sha256((descriptor["sha256"] + sha256(lock) + "runtime-v2").encode()).hexdigest()[:20]
    cache_root = ROOT / "desktop/runtime-cache/skills"
    cache_root.mkdir(parents=True, exist_ok=True)
    cache = cache_root / key
    if cache.is_dir():
        expected = json.loads((cache / "cache-manifest.json").read_text(encoding="utf-8"))
        for item in expected["files"]:
            path = cache / item["path"]
            if not path.is_file() or sha256(path) != item["sha256"]:
                raise RuntimeError(f"Runtime cache hash mismatch: {item['path']}")
        return cache
    with tempfile.TemporaryDirectory(prefix=f".{key}-", dir=cache_root) as temporary:
        stage = Path(temporary) / "runtime"
        python_root = stage / "python"
        python_root.mkdir(parents=True)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(python_root)
        (python_root / "python312._pth").write_text(
            "python312.zip\n.\nLib/site-packages\nimport site\n", encoding="utf-8")
        packages = python_root / "Lib/site-packages"
        _run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-index",
              "--find-links", str(ROOT / "wheelhouse"), "--require-hashes", "--no-compile",
              "--target", str(packages), "-r", str(lock)])
        shutil.copy2(lock, stage / "requirements.lock")
        _write_json(stage / "python-descriptor.json", descriptor)
        # pip stores the build command line here, including developer-local paths.
        for path in packages.rglob("direct_url.json"):
            path.unlink()
        _write_json(stage / "cache-manifest.json", {"files": records(stage)})
        stage.rename(cache)
    return cache


def _copy_graphviz(stage: Path) -> dict:
    descriptor = json.loads((ROOT / "desktop/runtime/graphviz-15.1.0.json").read_text(encoding="utf-8"))
    graphviz = Path(os.environ.get("SKILL_GRAPHVIZ_ROOT", str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Graphviz")))
    dot = graphviz / "bin/dot.exe"
    if not dot.is_file() or sha256(dot) != descriptor["dot_sha256"]:
        raise RuntimeError("The pinned Graphviz 15.1.0 runtime is missing or corrupt.")
    destination = stage / "runtime/graphviz"
    for name in ("bin", "lib", "share"):
        if (graphviz / name).is_dir():
            shutil.copytree(graphviz / name, destination / name)
    for name in ("LICENSE", "LICENSE.txt", "COPYING"):
        if (graphviz / name).is_file():
            shutil.copy2(graphviz / name, destination / name)
    return descriptor


def stage_skill(source: Path, stage: Path, *, skill_name: str, skill_version: str, provenance: dict) -> dict:
    source_records = [item for item in records(source) if "__pycache__" not in Path(item["path"]).parts
                      and Path(item["path"]).suffix not in {".pyc", ".pyo"}]
    shutil.copytree(source, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    for item in source_records:
        if sha256(stage / item["path"]) != item["sha256"]:
            raise RuntimeError(f"Source changed during packaging: {item['path']}")
    runtime = prepare_runtime(skill_name)
    shutil.copytree(runtime, stage / "runtime", ignore=shutil.ignore_patterns("cache-manifest.json"))
    graphviz = _copy_graphviz(stage) if skill_name == "huawei-doc-workflow" else None
    shutil.copy2(ROOT / "scripts/portable_skill_install.py", stage / "portable_install.py")
    shutil.copy2(ROOT / "scripts/portable_skill_run.py", stage / "portable_run.py")
    entry = ENTRIES[skill_name]
    _write_json(stage / "portable.json", {"skill_name": skill_name, "skill_version": skill_version,
                "entry": entry, "python": "runtime/python/python.exe", "graphviz": graphviz,
                "runtime_platform": "win_amd64", "python_version": "3.12.10"})
    (stage / "run.cmd").write_text(
        '@echo off\r\nsetlocal\r\n"%~dp0runtime\\python\\python.exe" -I -X utf8 -B "%~dp0portable_run.py" %*\r\nexit /b %errorlevel%\r\n', encoding="utf-8")
    (stage / "install.cmd").write_text(
        '@echo off\r\nsetlocal\r\n"%~dp0runtime\\python\\python.exe" -I -X utf8 -B "%~dp0portable_install.py" %*\r\nexit /b %errorlevel%\r\n', encoding="utf-8")
    (stage / "install.ps1").write_text(
        '& (Join-Path $PSScriptRoot "runtime/python/python.exe") -I -X utf8 -B (Join-Path $PSScriptRoot "portable_install.py") @args\nexit $LASTEXITCODE\n', encoding="utf-8")
    shutil.copy2(ROOT / "docs/THIRD_PARTY_NOTICES_WINDOWS.md", stage / "THIRD_PARTY_NOTICES.md")
    manifest = {
        "schema_version": 2, "skill_name": skill_name, "skill_version": skill_version,
        "engine_version": provenance["source_product_version"], "source_commit": provenance["source_commit"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "dependency_bundle_included": True,
        "platform": "Windows 10/11 x64", "python_version": "3.12.10", "entry": entry,
        "source_tree_sha256": hashlib.sha256(json.dumps(source_records, sort_keys=True).encode()).hexdigest(),
        "source_files": source_records,
        "dependency_lock_sha256": sha256(LOCKS[skill_name]), "graphviz_included": graphviz is not None,
        "files": records(stage),
    }
    _write_json(stage / MANIFEST, manifest)
    return manifest


def build_skill_archive(source: Path, output_dir: Path, *, skill_name: str, skill_version: str,
                        provenance: dict, overwrite: bool) -> tuple[Path, Path]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{skill_name}-{skill_version}.zip"
    if archive_path.exists() and not overwrite:
        raise SystemExit(f"refusing to overwrite existing archive: {archive_path}")
    # Keep staging paths short for Windows installations without LongPathsEnabled.
    with tempfile.TemporaryDirectory(prefix="skill-build-") as temporary:
        stage = Path(temporary) / skill_name
        stage_skill(source, stage, skill_name=skill_name, skill_version=skill_version, provenance=provenance)
        run_skill(stage, "--verify-runtime", cwd=Path(temporary))
        doctor = json.loads(run_skill(stage, "doctor", "--json", cwd=Path(temporary)).stdout)
        if doctor.get("skill_version") != skill_version:
            raise RuntimeError(f"Code version {doctor.get('skill_version')} differs from package version {skill_version}")
        fd, temporary_name = tempfile.mkstemp(prefix=".skill-", suffix=".zip", dir=output_dir)
        os.close(fd)
        temporary_archive = Path(temporary_name)
        try:
            with zipfile.ZipFile(temporary_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
                for path in sorted(stage.rglob("*")):
                    if path.is_file():
                        bundle.write(path, f"{skill_name}/{path.relative_to(stage).as_posix()}")
            verify_archive(temporary_archive)
            os.replace(temporary_archive, archive_path)
        finally:
            temporary_archive.unlink(missing_ok=True)
    digest_path = archive_path.with_suffix(".zip.sha256")
    digest_path.write_text(f"{sha256(archive_path)}  {archive_path.name}\n", encoding="utf-8")
    return archive_path, digest_path


def verify_archive(archive_path: Path) -> dict:
    from scripts.portable_skill_install import read_archive_manifest
    return read_archive_manifest(archive_path)


def run_skill(skill: Path, *args: str | Path, cwd: Path) -> subprocess.CompletedProcess:
    return _run([str(skill / "runtime/python/python.exe"), "-I", "-X", "utf8", "-B",
                 str(skill / "portable_run.py"), *(str(arg) for arg in args)], cwd=cwd,
                env=isolated_environment())
