"""Repository-independent, verified and rollback-safe Skill installation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile

MANIFEST = "SKILL_PACKAGE_MANIFEST.json"
SKILLS = {"huawei-doc-workflow", "rhetoric-deck-workflow"}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or ".." in path.parts or any(":" in p for p in path.parts):
        raise ValueError(f"unsafe package path: {value}")
    return path


def _validate_manifest(manifest: dict) -> None:
    if manifest.get("schema_version") != 2 or manifest.get("skill_name") not in SKILLS:
        raise ValueError("Unsupported or unrecognized portable skill manifest")
    if manifest.get("dependency_bundle_included") is not True or not manifest.get("skill_version"):
        raise ValueError("Package must include its runtime and version")
    paths = [str(_safe_relative(item["path"])) for item in manifest["files"]]
    if len({p.casefold() for p in paths}) != len(paths) or MANIFEST in paths:
        raise ValueError("Duplicate or recursive package manifest records")
    required = {"SKILL.md", "portable.json", "portable_run.py", "runtime/python/python.exe", "install.cmd"}
    if not required <= set(paths):
        raise ValueError("Incomplete portable skill package")


def read_archive_manifest(archive: Path) -> dict:
    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        if len(infos) > 20000 or sum(item.file_size for item in infos) > 1024 * 1024 * 1024:
            raise ValueError("Portable package exceeds resource limits")
        if any(item.file_size > 256 * 1024 * 1024 for item in infos):
            raise ValueError("Portable package member exceeds resource limits")
        names = [info.filename for info in infos if not info.is_dir()]
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError("Duplicate ZIP member")
        for info in infos:
            _safe_relative(info.filename.rstrip("/"))
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Symlinks are not allowed in skill packages")
        candidates = [name for name in names if name.endswith("/" + MANIFEST)]
        if len(candidates) != 1:
            raise ValueError("Expected exactly one skill manifest")
        manifest = json.loads(package.read(candidates[0]))
        _validate_manifest(manifest)
        prefix = manifest["skill_name"] + "/"
        expected = {prefix + item["path"] for item in manifest["files"]} | {prefix + MANIFEST}
        if set(names) != expected:
            raise ValueError("ZIP contents differ from package manifest")
        for item in manifest["files"]:
            data = package.read(prefix + item["path"])
            if len(data) != item["bytes"] or _digest(data) != item["sha256"]:
                raise ValueError(f"Package hash mismatch: {item['path']}")
        config = json.loads(package.read(prefix + "portable.json"))
        if any(config[key] != manifest[key] for key in ("skill_name", "skill_version", "entry")):
            raise ValueError("Portable configuration differs from package manifest")
    return manifest


def verify_directory(directory: Path) -> dict:
    manifest = json.loads((directory / MANIFEST).read_text(encoding="utf-8"))
    _validate_manifest(manifest)
    expected = {item["path"] for item in manifest["files"]} | {MANIFEST}
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("Installed contents differ from package manifest")
    for item in manifest["files"]:
        path = directory / item["path"]
        path.resolve().relative_to(directory.resolve())
        if path.is_symlink() or path.stat().st_size != item["bytes"] or _digest(path.read_bytes()) != item["sha256"]:
            raise ValueError(f"Installed hash mismatch: {item['path']}")
    return manifest


def doctor(directory: Path) -> dict:
    environment = os.environ.copy()
    for key in list(environment):
        if key.upper().startswith("PYTHON") or key.upper() == "VIRTUAL_ENV":
            environment.pop(key)
    environment["PATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32")
    environment["SKILL_NETWORK_DISABLED"] = "1"
    command = [str(directory / "runtime/python/python.exe"), "-I", "-X", "utf8", "-B",
               str(directory / "portable_run.py"), "doctor", "--json"]
    result = subprocess.run(command, cwd=directory.parent, env=environment, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=120)
    if result.returncode:
        raise ValueError(f"Packaged doctor failed ({result.returncode}): {result.stderr or result.stdout}")
    payload = json.loads(result.stdout)
    manifest = json.loads((directory / MANIFEST).read_text(encoding="utf-8"))
    if payload.get("skill_version") != manifest["skill_version"]:
        raise ValueError("Runtime-reported version differs from installed package")
    return payload


def install(source: Path, destination: Path, *, expected_name: str | None = None) -> dict:
    source = source.resolve()
    destination = destination.expanduser().resolve()
    manifest = read_archive_manifest(source) if source.is_file() else verify_directory(source)
    name = manifest["skill_name"]
    if expected_name is not None and name != expected_name:
        raise ValueError(f"Expected {expected_name}, got {name}")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / name
    if target.is_symlink():
        raise ValueError("Refusing to replace a symlinked installation")
    if source == target:
        doctor(target)
        return {"name": name, "version": manifest["skill_version"], "path": str(target), "doctor": "ok"}
    temporary = Path(tempfile.mkdtemp(prefix=".install-", dir=destination))
    backup = temporary / "previous"
    retained_backup = None
    try:
        staging = temporary / name
        if source.is_file():
            with zipfile.ZipFile(source) as package:
                package.extractall(temporary)
        else:
            shutil.copytree(source, staging)
        verify_directory(staging)
        doctor(staging)
        if target.exists():
            target.resolve().relative_to(destination)
            target.rename(backup)
        try:
            staging.rename(target)
        except BaseException:
            if backup.exists():
                backup.rename(target)
            raise
        if backup.exists():
            backup_root = destination / ".backups"
            backup_root.mkdir(exist_ok=True)
            retained_backup = backup_root / f"{name}-{uuid.uuid4().hex[:12]}"
            retained_backup.resolve().relative_to(destination)
            backup.rename(retained_backup)
    finally:
        # Preserve the old install if either rollback or persistent-backup
        # relocation failed; cleanup must never destroy the promised backup.
        if backup.exists():
            raise RuntimeError(f"Previous install retained for recovery: {backup}")
        shutil.rmtree(temporary)
    return {"name": name, "version": manifest["skill_version"], "path": str(target), "doctor": "ok",
            "previous_install_backup": str(retained_backup) if retained_backup else None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=Path.home() / ".codex/skills")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    if args.check:
        manifest = verify_directory(source)
        result = {"name": manifest["skill_name"], "version": manifest["skill_version"], "doctor": doctor(source)}
    else:
        result = install(source, args.dest)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        print(json.dumps({"ok": False, "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
