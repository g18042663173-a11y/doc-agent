from __future__ import annotations
# ruff: noqa: E402

import argparse
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DIST = ROOT / "dist"
ISS_FILE = ROOT / "installer.iss"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


@dataclass(frozen=True)
class InstallerPlan:
    zip_path: Path
    source_dir: Path
    output_exe: Path
    sha256_path: Path
    iscc: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the Inno Setup installer from the portable ZIP.")
    parser.add_argument("--zip", type=Path, help="Existing portable ZIP (default: latest document-workbench-*.zip).")
    parser.add_argument("--iscc", type=Path, help="Inno Setup Compiler executable (default: auto-detect).")
    parser.add_argument("--output-dir", type=Path, default=DIST)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.resolve()
    plan = _resolve_plan(args.zip, output_dir, args.iscc, args.overwrite)
    _compile(plan)
    return 0


def _resolve_plan(zip_arg: Path | None, output_dir: Path, iscc_arg: Path | None, overwrite: bool) -> InstallerPlan:
    zip_path = (zip_arg.resolve() if zip_arg else _find_latest_zip(output_dir))
    if not zip_path.is_file():
        raise SystemExit(f"portable ZIP not found: {zip_path}. Run scripts/package_document_workbench.py first.")

    source_dir = output_dir / zip_path.stem
    if source_dir.exists():
        shutil.rmtree(source_dir)
    source_dir.mkdir(parents=True)
    _extract_zip(zip_path, source_dir)

    workbench_exe = source_dir / "DocumentWorkbench.exe"
    if not workbench_exe.is_file():
        raise SystemExit(f"extracted portable directory is missing DocumentWorkbench.exe: {source_dir}")

    output_exe = output_dir / f"HuaweiDocumentGenerator-Setup-{VERSION}.exe"
    if output_exe.exists() and not overwrite:
        raise SystemExit(f"refusing to overwrite existing installer: {output_exe}")

    sha256_path = output_exe.with_suffix(".exe.sha256")
    if sha256_path.exists() and not overwrite:
        raise SystemExit(f"refusing to overwrite existing digest: {sha256_path}")

    iscc = (iscc_arg.resolve() if iscc_arg else _detect_iscc())
    if not iscc.is_file():
        print(
            "Inno Setup Compiler (ISCC.exe) not found. Install Inno Setup 6 from "
            "https://jrsoftware.org/isdl.php or pass --iscc.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return InstallerPlan(
        zip_path=zip_path,
        source_dir=source_dir,
        output_exe=output_exe,
        sha256_path=sha256_path,
        iscc=iscc,
    )


def _find_latest_zip(output_dir: Path) -> Path:
    candidates = sorted(
        output_dir.glob(f"document-workbench-windows-x64-{VERSION}.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else output_dir / f"document-workbench-windows-x64-{VERSION}.zip"


def _extract_zip(zip_path: Path, destination: Path) -> None:
    root = destination.resolve()
    seen_targets: set[str] = set()
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                target = _archive_member_target(member, root, seen_targets)
                if target is None:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except zipfile.BadZipFile as exc:
        raise SystemExit(f"portable ZIP is invalid: {zip_path}") from exc


def _archive_member_target(member: zipfile.ZipInfo, root: Path, seen_targets: set[str]) -> Path | None:
    name = member.filename
    path = PurePosixPath(name)
    mode = member.external_attr >> 16
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or path.is_absolute()
        or ".." in path.parts
        or stat.S_ISLNK(mode)
    ):
        raise SystemExit(f"portable ZIP contains an unsafe member path: {name}")
    if member.is_dir():
        return None

    # Generated archives have one product-directory prefix. Strip it only after
    # validating the POSIX member name, then enforce that the result stays inside
    # the installer staging directory on Windows and Unix alike.
    parts = path.parts
    relative = Path(*parts[1:]) if len(parts) > 1 else Path(parts[0])
    target = (root / relative).resolve()
    try:
        relative_target = target.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"portable ZIP member escapes the staging directory: {name}") from exc
    target_key = relative_target.as_posix().casefold()
    if target_key in seen_targets:
        raise SystemExit(f"portable ZIP contains duplicate extraction targets: {name}")
    seen_targets.add(target_key)
    return target


def _detect_iscc() -> Path:
    for root in (
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Inno Setup 6",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Inno Setup 6",
        Path.home() / "Inno Setup 6",
    ):
        candidate = root / "ISCC.exe"
        if candidate.is_file():
            return candidate
    resolved = shutil.which("iscc") or shutil.which("ISCC")
    return Path(resolved) if resolved else Path("ISCC.exe")


def _compile(plan: InstallerPlan) -> None:
    command = [
        str(plan.iscc),
        f"/DAppVersion={VERSION}",
        f"/DSourceDir={plan.source_dir}",
        f"/DOutputDir={plan.output_exe.parent}",
        str(ISS_FILE),
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"ISCC compilation failed with exit code {result.returncode}")
    if not plan.output_exe.is_file():
        raise SystemExit(f"ISCC succeeded but installer is missing: {plan.output_exe}")

    digest = _sha256(plan.output_exe)
    plan.sha256_path.write_text(f"{digest}  {plan.output_exe.name}\n", encoding="utf-8")
    print(f"installer: {plan.output_exe}")
    print(f"sha256: {digest}")
    print(f"bytes: {plan.output_exe.stat().st_size}")
    print(f"source: {plan.zip_path.name}")


def _sha256(path: Path) -> str:
    digest = sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
