"""Synchronize and package the standalone huawei-doc-workflow Codex skill."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.portable_skill_runtime import build_skill_archive, run_skill
SKILL_NAME = "huawei-doc-workflow"
SKILL_VERSION = "1.1.0"
SKILL_DIR = ROOT / "skills" / SKILL_NAME
ENGINE_DIR = SKILL_DIR / "scripts" / "engine"

APP_DIRECTORIES = (
    "assets",
    "ir",
    "lint",
    "parsers",
    "rendering",
    "security",
    "template",
    "visual",
)
APP_FILES = ("__init__.py",)
GENERATION_FILES = ("__init__.py", "layout_policy.py")
SCHEMA_FILES = (
    "asset_manifest.schema.json",
    "asset_usage_audit.schema.json",
    "deck_ir.schema.json",
    "document_ir.schema.json",
    "schema_history.json",
    "template_plan.schema.json",
    "template_profile.schema.json",
    "template_replacement_audit.schema.json",
    "visual_plan.schema.json",
    "visual_selection_audit.schema.json",
    "word_ir.schema.json",
)
EXAMPLE_FILES = (
    "deck_few_shot_architecture_v19.json",
    "deck_few_shot_composite_v19.json",
    "deck_few_shot_table_v19.json",
    "deck_valid_01_minimal.json",
    "deck_valid_full.json",
    "word_valid_01_plain.json",
    "word_valid_03_table.json",
    "word_valid_05_document_control.json",
)
FORBIDDEN_PARTS = {
    ".env",
    "desktop",
    "generators",
    "static",
    "web_api.py",
    "wheelhouse",
}
FORBIDDEN_TEXT = (
    "C:\\Users\\",
    "C:/Users/",
    "/Users/",
    "/home/",
    "app.generators",
    "from flask",
    "import flask",
    "from waitress",
    "import waitress",
)
SAFE_SUFFIXES = {".json", ".md", ".py", ".txt", ".yaml"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize the deterministic engine snapshot and build a portable Codex skill ZIP."
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Refresh scripts/engine from the canonical backend before verification.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify the skill and engine snapshot without creating a ZIP.",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sync:
        synchronize_engine_snapshot()
    verify_skill_source()
    if args.check_only:
        print(f"skill source verified: {SKILL_DIR}")
        return 0
    archive, digest = build_archive(args.output_dir, overwrite=args.overwrite)
    print(f"archive: {archive}")
    print(f"sha256: {digest}")
    return 0


def synchronize_engine_snapshot() -> Path:
    """Refresh the checked-in portable engine from explicitly allow-listed sources."""
    _assert_within(ENGINE_DIR, SKILL_DIR)
    ENGINE_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("app", "schemas", "examples"):
        target = ENGINE_DIR / name
        _assert_within(target, ENGINE_DIR)
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, str | int]] = []
    for filename in APP_FILES:
        _copy_record(ROOT / "backend" / "app" / filename, ENGINE_DIR / "app" / filename, records)
    for directory in APP_DIRECTORIES:
        source_root = ROOT / "backend" / "app" / directory
        for source in _source_files(source_root):
            relative = source.relative_to(ROOT / "backend" / "app")
            _copy_record(source, ENGINE_DIR / "app" / relative, records)
    for filename in GENERATION_FILES:
        source = ROOT / "backend" / "app" / "generation" / filename
        _copy_record(source, ENGINE_DIR / "app" / "generation" / filename, records)
    for filename in SCHEMA_FILES:
        source = ROOT / "backend" / "schemas" / filename
        _copy_record(source, ENGINE_DIR / "schemas" / filename, records)
    for filename in EXAMPLE_FILES:
        source = ROOT / "samples" / "ir" / filename
        _copy_record(source, ENGINE_DIR / "examples" / filename, records)
    _copy_record(ROOT / "VERSION", ENGINE_DIR / "VERSION", records)

    manifest = {
        "schema_version": 1,
        "skill_name": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "source_product_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "source_commit": _git_output("rev-parse", "HEAD"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": sorted(records, key=lambda item: str(item["path"])),
    }
    manifest_path = ENGINE_DIR / "runtime_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"engine snapshot synchronized: {manifest_path}")
    return manifest_path


def verify_skill_source() -> dict:
    required = (
        SKILL_DIR / "SKILL.md",
        SKILL_DIR / "agents" / "openai.yaml",
        SKILL_DIR / "scripts" / "workflow.py",
        ENGINE_DIR / "runtime_manifest.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("skill source is incomplete:\n- " + "\n- ".join(missing))

    manifest = json.loads((ENGINE_DIR / "runtime_manifest.json").read_text(encoding="utf-8"))
    expected_paths: set[str] = set()
    problems: list[str] = []
    for record in manifest.get("files", []):
        relative = Path(str(record["path"]))
        source_relative = Path(str(record["source"]))
        snapshot = ENGINE_DIR / relative
        source = ROOT / source_relative
        expected_paths.add(relative.as_posix())
        if not snapshot.is_file():
            problems.append(f"snapshot file missing: {relative.as_posix()}")
            continue
        actual_snapshot = _sha256(snapshot)
        if actual_snapshot != record["sha256"]:
            problems.append(f"snapshot hash drift: {relative.as_posix()}")
        if not source.is_file():
            problems.append(f"canonical source missing: {source_relative.as_posix()}")
            continue
        if _sha256(source) != record["sha256"]:
            problems.append(
                f"canonical source changed; run --sync: {source_relative.as_posix()}"
            )

    actual_paths = {
        path.relative_to(ENGINE_DIR).as_posix()
        for path in ENGINE_DIR.rglob("*")
        if path.is_file() and path.name != "runtime_manifest.json" and "__pycache__" not in path.parts
    }
    if actual_paths != expected_paths:
        extra = sorted(actual_paths - expected_paths)
        absent = sorted(expected_paths - actual_paths)
        if extra:
            problems.append("untracked engine files: " + ", ".join(extra))
        if absent:
            problems.append("manifest-only engine files: " + ", ".join(absent))

    for path in _skill_files():
        relative = path.relative_to(SKILL_DIR)
        lowered_parts = {part.lower() for part in relative.parts}
        forbidden = sorted(lowered_parts & FORBIDDEN_PARTS)
        if forbidden:
            problems.append(f"forbidden path in skill: {relative.as_posix()}")
        is_engine_version = relative.as_posix() == "scripts/engine/VERSION"
        if path.suffix.lower() not in SAFE_SUFFIXES and not is_engine_version:
            problems.append(f"unexpected file type in skill: {relative.as_posix()}")
        if path.suffix.lower() in SAFE_SUFFIXES:
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN_TEXT:
                if needle in text:
                    problems.append(f"forbidden runtime dependency {needle!r} in {relative.as_posix()}")
    if problems:
        raise SystemExit("skill verification failed:\n- " + "\n- ".join(sorted(set(problems))))
    return manifest


def build_archive(output_dir: Path, *, overwrite: bool) -> tuple[Path, Path]:
    provenance = verify_skill_source()
    return build_skill_archive(SKILL_DIR, output_dir, skill_name=SKILL_NAME,
                               skill_version=SKILL_VERSION, provenance=provenance, overwrite=overwrite)


def verify_isolated_archive(archive_path: Path, *, additional_deck_ir: dict | None = None) -> dict:
    """Render Word and the full DeckIR sample through the extracted portable entry."""
    from scripts.portable_skill_runtime import verify_archive
    verify_archive(archive_path)
    with tempfile.TemporaryDirectory(prefix="generation-qa-") as temporary_name:
        temporary = Path(temporary_name)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(temporary)
        skill = temporary / SKILL_NAME
        runtime = json.loads(run_skill(skill, "--verify-runtime", cwd=temporary).stdout)
        cases = []
        for target, sample, artifact in (("word", "word_valid_01_plain.json", "document.docx"),
                                         ("deck", "deck_valid_full.json", "deck.pptx")):
            work = temporary / target
            run_skill(skill, "validate", "--target", target, "--draft",
                      skill / "scripts/engine/examples" / sample, "--output-dir", work, cwd=temporary)
            run_skill(skill, "finalize", "--target", target, "--ir", work / "validated_ir.json",
                      "--output-dir", work, cwd=temporary)
            if not (work / artifact).is_file():
                raise RuntimeError(f"Portable generation did not produce {artifact}")
            report = json.loads((work / "report.json").read_text(encoding="utf-8"))
            if not report["summary"]["pass"]:
                raise RuntimeError(f"Portable {target} lint failed")
            cases.append({"target": target, "artifact": artifact, "lint_pass": True})
        if additional_deck_ir is not None:
            draft = temporary / "cross-skill.json"
            draft.write_text(json.dumps(additional_deck_ir, ensure_ascii=False), encoding="utf-8")
            work = temporary / "cross-skill"
            run_skill(skill, "validate", "--target", "deck", "--draft", draft, "--output-dir", work, cwd=temporary)
            run_skill(skill, "finalize", "--target", "deck", "--ir", work / "validated_ir.json",
                      "--output-dir", work, cwd=temporary)
            if not (work / "deck.pptx").is_file():
                raise RuntimeError("Cross-skill IR did not produce a deck")
            cases.append({"target": "cross-skill-deck", "artifact": "deck.pptx", "lint_pass": True})
        return {"pass": True, "runtime": runtime, "cases": cases}


def _source_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix.lower() in {".json", ".py", ".txt"}
    )


def _copy_record(source: Path, destination: Path, records: list[dict[str, str | int]]) -> None:
    if not source.is_file():
        raise SystemExit(f"required engine source is missing: {source}")
    _assert_within(destination, ENGINE_DIR)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    records.append(
        {
            "path": destination.relative_to(ENGINE_DIR).as_posix(),
            "source": source.relative_to(ROOT).as_posix(),
            "bytes": destination.stat().st_size,
            "sha256": _sha256(destination),
        }
    )


def _skill_files() -> list[Path]:
    return sorted(
        path
        for path in SKILL_DIR.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix.lower() not in {".pyc", ".pyo"}
    )


def _assert_within(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise SystemExit(f"refusing filesystem operation outside {resolved_root}: {resolved_path}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_skill(destination: Path) -> Path:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / SKILL_NAME
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        SKILL_DIR,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    return target


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


if __name__ == "__main__":
    raise SystemExit(main())
