"""Install or check the two independently portable Agent skills. No Docker."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.portable_skill_install import doctor, install, read_archive_manifest, verify_directory
from scripts.portable_skill_runtime import sha256

DEFAULT_DEST = Path.home() / ".codex/skills"
MANIFEST_NAME = "agent_kit_manifest.json"
SIMPLE_ZIPS = {"huawei-doc-workflow": "生成.zip", "rhetoric-deck-workflow": "模仿.zip"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--from-zip", type=Path, help="Directory containing the two short-name ZIPs or versioned ZIPs.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--python", type=Path, default=Path(sys.executable), help=argparse.SUPPRESS)
    return parser


def _resolve_skill_zip(zip_dir: Path, skill_name: str, skill_version: str | None = None) -> Path:
    short = zip_dir / SIMPLE_ZIPS[skill_name]
    if short.is_file():
        return short
    candidates = list(zip_dir.glob(f"{skill_name}-*.zip"))
    if skill_version:
        exact = zip_dir / f"{skill_name}-{skill_version}.zip"
        if exact.is_file():
            return exact
    if len(candidates) != 1:
        raise ValueError(f"Expected one {skill_name} archive; provide {SIMPLE_ZIPS[skill_name]} to select explicitly.")
    return candidates[0]


def _verify_archive_digest(archive: Path) -> None:
    digest = archive.with_suffix(".zip.sha256")
    if not digest.is_file():
        raise ValueError(f"Missing archive digest: {digest.name}")
    if digest.read_text(encoding="utf-8").split()[0].lower() != sha256(archive):
        raise ValueError(f"Archive digest mismatch: {archive.name}")


def _install_from_zip(zip_dir: Path, destination: Path, skill_name: str, skill_version: str | None = None) -> Path:
    archive = _resolve_skill_zip(zip_dir.expanduser().resolve(), skill_name, skill_version)
    _verify_archive_digest(archive)
    install(archive, destination, expected_name=skill_name)
    return destination.resolve() / skill_name


def install_kit(destination: Path, *, zip_dir: Path | None = None) -> dict:
    destination = destination.expanduser().resolve()
    if zip_dir is None:
        from scripts import package_huawei_doc_skill as generation, package_rhetoric_deck_skill as imitation
        with tempfile.TemporaryDirectory(prefix="agent-kit-build-") as temporary:
            archives = Path(temporary)
            generation.build_archive(archives, overwrite=False)
            imitation.build_archive(archives, imitation.verify_skill_source(), overwrite=False)
            return install_kit(destination, zip_dir=archives)
    zip_dir = zip_dir.expanduser().resolve()
    archives = {name: _resolve_skill_zip(zip_dir, name) for name in SIMPLE_ZIPS}
    for name, archive in archives.items():
        _verify_archive_digest(archive)
        if read_archive_manifest(archive)["skill_name"] != name:
            raise ValueError(f"Unexpected skill in {archive.name}")
    skills = [install(archive, destination, expected_name=name) for name, archive in archives.items()]
    report = {"schema_version": 2, "kit": "huawei-agent-kit", "ok": True,
              "installed_at_utc": datetime.now(timezone.utc).isoformat(), "destination": str(destination),
              "docker_required": False, "source": "zip", "skills": skills,
              "workbench": "separate portable ZIP via scripts/package_document_workbench.py"}
    (destination / MANIFEST_NAME).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def check_kit(destination: Path, *, python: Path | None = None, after_install: dict | None = None) -> dict:
    destination = destination.expanduser().resolve()
    report = dict(after_install or {"schema_version": 2, "kit": "huawei-agent-kit", "destination": str(destination),
                                   "docker_required": False, "workbench": "separate portable ZIP", "skills": []})
    checked, problems = [], []
    for name in SIMPLE_ZIPS:
        directory = destination / name
        try:
            manifest = verify_directory(directory)
            doctor(directory)
            checked.append({"name": name, "version": manifest["skill_version"], "path": str(directory), "doctor": "ok"})
        except (ValueError, OSError) as error:
            problems.append(f"{name}: {error}")
    report.update(ok=not problems, skills=checked)
    if problems:
        report["problems"] = problems
    return report


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = check_kit(args.dest) if args.check else install_kit(args.dest, zip_dir=args.from_zip)
    except (ValueError, OSError) as error:
        report = {"ok": False, "message": str(error)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
