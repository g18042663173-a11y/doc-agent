from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from email.parser import Parser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write an auditable SHA-256 manifest for downloaded wheels.")
    parser.add_argument("--wheelhouse", type=Path, default=ROOT / "wheelhouse")
    parser.add_argument("--requirements", type=Path, default=ROOT / "requirements.txt")
    parser.add_argument("--manifest", type=Path, default=ROOT / "docs" / "wheelhouse-win312-manifest.json")
    parser.add_argument("--lock", type=Path, default=ROOT / "requirements-win312.lock")
    parser.add_argument("--platform", default="win_amd64")
    parser.add_argument("--python-version", default="3.12")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    wheels = sorted(args.wheelhouse.glob("*.whl"), key=lambda path: path.name.lower())
    if not wheels:
        raise SystemExit(f"no wheels found in {args.wheelhouse}")

    records = [_wheel_record(path) for path in wheels]
    manifest = {
        "schema_version": 1,
        "target": {
            "platform": args.platform,
            "python_version": args.python_version,
            "implementation": "CPython",
        },
        "source_requirements": args.requirements.relative_to(ROOT).as_posix(),
        "source_requirements_sha256": _sha256(args.requirements),
        "hash_algorithm": "sha256",
        "wheel_count": len(records),
        "wheels": records,
        "verification_boundary": "Hashes were generated from downloaded Windows wheels on macOS; offline installation still requires Windows true-machine validation.",
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Generated from docs/wheelhouse-win312-manifest.json.",
        "# Target: CPython 3.12 / win_amd64. Do not claim installation success until Windows true-machine validation.",
    ]
    lines.extend(
        f"{record['name']}=={record['version']} --hash=sha256:{record['sha256']}"
        for record in sorted(records, key=lambda value: value["name"].lower())
    )
    args.lock.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} wheel hashes")
    return 0


def _wheel_record(path: Path) -> dict[str, str | int]:
    with zipfile.ZipFile(path) as package:
        metadata_name = next(name for name in package.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(package.read(metadata_name).decode("utf-8", errors="replace"))
    return {
        "name": metadata["Name"],
        "version": metadata["Version"],
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
