"""Synchronize, verify, and package the standalone rhetoric-deck-workflow skill."""

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
SKILL_NAME = "rhetoric-deck-workflow"
SKILL_VERSION = "2.0.0"
SKILL_DIR = ROOT / "skills" / SKILL_NAME
DIRECT_COPIES = {
    ROOT / "backend/app/security/office_package.py": SKILL_DIR / "engine/security/office_package.py",
    ROOT / "backend/app/template/text_fit.py": SKILL_DIR / "engine/fit/text_fit.py",
    ROOT / "backend/app/cli/errors.py": SKILL_DIR / "engine/shared/cli_errors.py",
    ROOT / "backend/schemas/deck_ir.schema.json": SKILL_DIR / "schemas/deck_ir.schema.json",
}
FORBIDDEN_PARTS = {
    "assets",
    "generators",
    "lint",
    "rendering",
    "static",
    "templates",
    "web",
    "web_api.py",
    "wheelhouse",
    "wpf",
}
FORBIDDEN_TEXT = (
    "C:\\Users\\",
    "C:/Users/",
    "/Users/",
    "/home/",
    "app.generators",
    "from flask",
    "import flask",
    "from fastapi",
    "import fastapi",
    "from PIL",
    "import PIL",
)
SAFE_SUFFIXES = {".docx", ".json", ".md", ".pptx", ".py", ".txt", ".yaml"}
MAX_UNCOMPRESSED_SKILL_BYTES = 2 * 1024 * 1024


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="Refresh frozen direct-copy files.")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sync:
        synchronize_direct_copies()
    provenance = verify_skill_source()
    if args.check_only:
        print(f"skill source verified: {SKILL_DIR}")
        return 0
    archive, digest = build_archive(args.output_dir, provenance, overwrite=args.overwrite)
    verify_isolated_archive(archive)
    print(f"archive: {archive}")
    print(f"sha256: {digest}")
    return 0


def synchronize_direct_copies() -> Path:
    records: list[dict[str, str | int]] = []
    for source, destination in DIRECT_COPIES.items():
        if not source.is_file():
            raise SystemExit(f"required source missing: {source}")
        _assert_within(destination, SKILL_DIR)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append(
            {
                "path": destination.relative_to(SKILL_DIR).as_posix(),
                "source": source.relative_to(ROOT).as_posix(),
                "bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
                "reuse_mode": "direct_copy",
            }
        )
    manifest = {
        "schema_version": 1,
        "skill_name": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "source_product_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "source_commit": _git_output("rev-parse", "HEAD"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": sorted(records, key=lambda item: str(item["path"])),
    }
    target = SKILL_DIR / "engine/runtime_manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def verify_skill_source() -> dict:
    required = (
        SKILL_DIR / "SKILL.md",
        SKILL_DIR / "README.md",
        SKILL_DIR / "VERSION",
        SKILL_DIR / "agents/openai.yaml",
        SKILL_DIR / "bin/rdw.py",
        SKILL_DIR / "engine/runtime_manifest.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("skill source is incomplete:\n- " + "\n- ".join(missing))
    provenance = json.loads((SKILL_DIR / "engine/runtime_manifest.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    for record in provenance.get("files", []):
        target = SKILL_DIR / str(record["path"])
        source = ROOT / str(record["source"])
        if not target.is_file() or _sha256(target) != record["sha256"]:
            problems.append(f"frozen copy drift: {record['path']}")
        if not source.is_file() or _sha256(source) != record["sha256"]:
            problems.append(f"canonical source changed; run --sync: {record['source']}")
    files = _skill_files()
    total_bytes = sum(path.stat().st_size for path in files)
    if total_bytes > MAX_UNCOMPRESSED_SKILL_BYTES:
        problems.append(f"skill exceeds {MAX_UNCOMPRESSED_SKILL_BYTES} byte limit: {total_bytes}")
    for path in files:
        relative = path.relative_to(SKILL_DIR)
        lowered = {part.casefold() for part in relative.parts}
        if lowered & FORBIDDEN_PARTS:
            problems.append(f"forbidden path: {relative.as_posix()}")
        if path.suffix.casefold() not in SAFE_SUFFIXES and path.name != "VERSION":
            problems.append(f"unexpected file type: {relative.as_posix()}")
        if path.suffix.casefold() in {".py", ".md", ".json", ".yaml", ".txt"}:
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN_TEXT:
                if needle in text and relative.as_posix() != "engine/fit/text_fit.py":
                    problems.append(f"forbidden dependency/text {needle!r}: {relative.as_posix()}")
    if problems:
        raise SystemExit("skill verification failed:\n- " + "\n- ".join(sorted(set(problems))))
    return provenance


def build_archive(output_dir: Path, provenance: dict, *, overwrite: bool) -> tuple[Path, Path]:
    verify_skill_source()
    return build_skill_archive(SKILL_DIR, output_dir, skill_name=SKILL_NAME,
                               skill_version=SKILL_VERSION, provenance=provenance, overwrite=overwrite)


def verify_isolated_archive(archive_path: Path) -> dict:
    from scripts.portable_skill_runtime import verify_archive
    verify_archive(archive_path)
    with tempfile.TemporaryDirectory(prefix="rdw-isolated-") as temporary_name:
        temporary = Path(temporary_name)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(temporary)
        skill = temporary / SKILL_NAME
        rdw = skill / "bin/rdw.py"
        def run(*args: str | Path) -> subprocess.CompletedProcess[str]:
            return run_skill(skill, *args, cwd=temporary)

        runtime = json.loads(run("--verify-runtime").stdout)

        run("doctor", "--json")
        source_work = temporary / "source-work"
        run("extract", "--source", skill / "samples/source_sample.pptx", "--out", source_work)
        run("seal", "--workdir", source_work, "--skeleton", source_work / "extract_pack/skeleton_draft.json")
        run(
            "plan", "--workdir", source_work,
            "--skeleton", source_work / "sealed/skeleton.sealed.json",
            "--material", skill / "samples/material_sample.docx",
            "--render-mode", "source-shell",
        )
        _write_smoke_content(source_work, temporary / "source-content.json")
        source_out = temporary / "source-out"
        run("finalize", "--workdir", source_work, "--content", temporary / "source-content.json", "--out", source_out)
        if not (source_out / "deck.pptx").is_file():
            raise SystemExit("isolated source-shell smoke did not produce deck.pptx")

        deck_work = temporary / "deck-work"
        deck_work.mkdir()
        run(
            "plan", "--workdir", deck_work, "--pattern", "review_solution",
            "--material", skill / "samples/material_sample.docx", "--render-mode", "deck-ir",
        )
        _write_smoke_content(deck_work, temporary / "deck-content.json")
        deck_out = temporary / "deck-out"
        run("finalize", "--workdir", deck_work, "--content", temporary / "deck-content.json", "--out", deck_out)
        if not (deck_out / "deck_ir.json").is_file() or (deck_out / "deck.pptx").exists():
            raise SystemExit("isolated deck-ir smoke did not produce DeckIR-only output")
        return {"pass": True, "runtime": runtime, "cases": ["source-shell", "deck-ir"],
                "deck_ir": json.loads((deck_out / "deck_ir.json").read_text(encoding="utf-8"))}


def _write_smoke_content(workdir: Path, destination: Path) -> None:
    skeleton = json.loads((workdir / "fill_pack/skeleton.json").read_text(encoding="utf-8"))
    material = json.loads((workdir / "fill_pack/material.json").read_text(encoding="utf-8"))
    accepted = {
        item["page_id"]
        for item in json.loads((workdir / "fill_pack/fit_report.json").read_text(encoding="utf-8"))["pages"]
        if item["verdict"] != "reject"
    }
    lines = [line.strip() for line in material["raw_text"].splitlines() if line.strip()]
    # Classification is page chrome, not reusable business content. Keep the
    # synthetic fill grounded in the sample's actual topic and body instead.
    body_values = [line for line in lines[1:] if not line.startswith(("密级：", "密级:"))][:2] or [material["title"]]
    short_value = material["title"].split("：", 1)[-1]
    evidence_refs = [item["id"] for item in material.get("evidence", [])]
    pages = []
    for page in skeleton["pages"]:
        if page["page_id"] not in accepted:
            continue
        slots = []
        for slot in page["slots"]:
            if slot["type"] == "title":
                value: str | list[str] = material["title"]
            elif slot["type"] in {"bullet_list", "table_cell", "node_label"}:
                value = body_values[: slot["cardinality"]["max"]]
            else:
                value = short_value
            slots.append({"slot_id": slot["slot_id"], "value": value, "evidence_refs": evidence_refs})
        pages.append({"page_id": page["page_id"], "slots": slots})
    destination.write_text(
        json.dumps({"format": "fill_content", "version": "2.0", "pages": pages}, ensure_ascii=False),
        encoding="utf-8",
    )


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


def _skill_files() -> list[Path]:
    return sorted(
        path
        for path in SKILL_DIR.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix.casefold() not in {".pyc", ".pyo"}
    )


def _assert_within(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise SystemExit(f"refusing operation outside {root.resolve()}: {path.resolve()}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
