"""Create a portable Windows development snapshot of this repository.

The archive contains the current working tree, including intentional untracked
source files, the Windows CPython 3.12 wheelhouse, and enough Git metadata to
continue on the same branch. It deliberately excludes regenerable outputs,
local virtual environments, caches, environment files, and local Git config.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Iterable
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ALWAYS_EXCLUDED_TOP_LEVEL = frozenset(
    {
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "dist",
        "output",
        "MIGRATION_PACKAGE_MANIFEST.json",
    }
)
EXCLUDED_GIT_PATHS = frozenset(
    {".git/config", ".git/config.worktree", ".git/info/exclude"}
)
EXCLUDED_GIT_PREFIXES = (
    ".git/hooks/",
    ".git/logs/",
    ".git/worktrees/",
)
EXCLUDED_FILE_SUFFIXES = frozenset({".pyc", ".p12", ".pfx", ".pem", ".key"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a Windows development ZIP with source, Git metadata, and wheelhouse."
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--name",
        help="ZIP filename. Defaults to huawei_document_generator_windows_dev_YYYYMMDD.zip.",
    )
    parser.add_argument(
        "--without-git",
        action="store_true",
        help="Do not include sanitized .git metadata. The extracted source will not retain history.",
    )
    parser.add_argument(
        "--without-wheelhouse",
        action="store_true",
        help="Do not include wheelhouse/. The archive will require a separately transferred wheelhouse.",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    name = args.name or f"huawei_document_generator_windows_dev_{datetime.now():%Y%m%d}.zip"
    archive_name = _archive_name(name)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / archive_name
    digest_path = archive_path.with_suffix(archive_path.suffix + ".sha256")

    if archive_path.exists() and not args.overwrite:
        raise SystemExit(f"refusing to overwrite existing archive: {archive_path}")

    include_git = not args.without_git
    include_wheelhouse = not args.without_wheelhouse
    files, skipped_symlinks = _collect_package_files(
        include_git=include_git,
        include_wheelhouse=include_wheelhouse,
    )
    if not files:
        raise SystemExit("no package files were selected")

    archive_root = archive_path.stem
    manifest = _manifest_base(
        archive_name=archive_name,
        archive_root=archive_root,
        include_git=include_git,
        include_wheelhouse=include_wheelhouse,
        skipped_symlinks=skipped_symlinks,
    )
    records: list[dict[str, str | int]] = []
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path, relative_path in files:
            archive.write(path, arcname=f"{archive_root}/{relative_path.as_posix()}")
            records.append(_file_record(path, relative_path))
        if include_git:
            git_exclude_path = Path(".git") / "info" / "exclude"
            git_exclude = _packaged_git_exclude().encode("utf-8")
            archive.writestr(f"{archive_root}/{git_exclude_path.as_posix()}", git_exclude)
            records.append(_bytes_record(git_exclude_path, git_exclude))
        manifest["files"] = records
        archive.writestr(
            f"{archive_root}/MIGRATION_PACKAGE_MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    archive_digest = _sha256(archive_path)
    digest_path.write_text(f"{archive_digest}  {archive_path.name}\n", encoding="utf-8")
    print(f"archive: {archive_path}")
    print(f"sha256: {digest_path}")
    print(f"files: {len(files)}")
    return 0


def _archive_name(value: str) -> str:
    candidate = Path(value)
    if candidate.name != value:
        raise SystemExit("--name must be a filename, not a path")
    if candidate.suffix.lower() != ".zip":
        return f"{candidate.name}.zip"
    return candidate.name


def _collect_package_files(
    *,
    include_git: bool,
    include_wheelhouse: bool,
) -> tuple[list[tuple[Path, Path]], list[str]]:
    files: list[tuple[Path, Path]] = []
    skipped_symlinks: list[str] = []
    for directory, directory_names, file_names in ROOT.walk(top_down=True):
        relative_directory = directory.relative_to(ROOT)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if not _should_exclude(
                relative_directory / name,
                include_git=include_git,
                include_wheelhouse=include_wheelhouse,
            )
        )
        for name in sorted(file_names):
            path = directory / name
            relative_path = path.relative_to(ROOT)
            if _should_exclude(
                relative_path,
                include_git=include_git,
                include_wheelhouse=include_wheelhouse,
            ):
                continue
            if path.is_symlink():
                skipped_symlinks.append(relative_path.as_posix())
                continue
            if path.is_file():
                files.append((path, relative_path))
    return files, skipped_symlinks


def _should_exclude(
    relative_path: Path,
    *,
    include_git: bool,
    include_wheelhouse: bool,
) -> bool:
    parts = relative_path.parts
    if not parts:
        return False
    if parts[0] in ALWAYS_EXCLUDED_TOP_LEVEL:
        return True
    if parts[0] == "wheelhouse" and not include_wheelhouse:
        return True
    if parts[0] == ".git":
        if not include_git:
            return True
        normalized = relative_path.as_posix()
        if normalized in EXCLUDED_GIT_PATHS:
            return True
        if any(normalized.startswith(prefix) for prefix in EXCLUDED_GIT_PREFIXES):
            return True
    if "__pycache__" in parts:
        return True

    name = relative_path.name
    if name == ".DS_Store" or name.startswith(".coverage"):
        return True
    if name == ".env" or name.startswith(".env."):
        return True
    return relative_path.suffix.lower() in EXCLUDED_FILE_SUFFIXES


def _manifest_base(
    *,
    archive_name: str,
    archive_root: str,
    include_git: bool,
    include_wheelhouse: bool,
    skipped_symlinks: Iterable[str],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive": {
            "filename": archive_name,
            "root_directory": archive_root,
            "git_metadata_included": include_git,
            "wheelhouse_included": include_wheelhouse,
        },
        "source": {
            "branch": _git_output("branch", "--show-current"),
            "head": _git_output("rev-parse", "HEAD"),
            "head_subject": _git_output("log", "-1", "--format=%s"),
            "working_tree_status": _git_output("status", "--short").splitlines(),
        },
        "intentional_exclusions": {
            "top_level": sorted(ALWAYS_EXCLUDED_TOP_LEVEL),
            "secret_or_machine_local": [".env", ".env.*", ".pem", ".key", ".p12", ".pfx"],
            "git": [
                ".git/config",
                ".git/config.worktree",
                ".git/hooks/",
                ".git/logs/",
                ".git/info/exclude (recreated for archive metadata)",
            ],
        },
        "skipped_symlinks": sorted(skipped_symlinks),
    }


def _git_output(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unavailable"
    return result.stdout.strip()


def _file_record(path: Path, relative_path: Path) -> dict[str, str | int]:
    return {
        "path": relative_path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _bytes_record(relative_path: Path, content: bytes) -> dict[str, str | int]:
    return {
        "path": relative_path.as_posix(),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _packaged_git_exclude() -> str:
    source = ROOT / ".git" / "info" / "exclude"
    content = source.read_text(encoding="utf-8", errors="replace") if source.is_file() else ""
    if content and not content.endswith("\n"):
        content += "\n"
    return (
        content
        + "\n# Archive metadata is intentionally outside project source.\n"
        + "MIGRATION_PACKAGE_MANIFEST.json\n"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
