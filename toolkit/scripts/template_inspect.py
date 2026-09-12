"""Write the machine and human readable template inventories used by template rendering."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.template.ppt_template_structure import extract_ppt_template_structure, write_ppt_template_structure
from app.template.profile import extract_template_profile, write_template_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect a safe PPTX template without modifying it.")
    parser.add_argument("template", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def inspect_template(template_path: Path, output_dir: Path) -> dict[str, Path]:
    profile = extract_template_profile(template_path)
    structure = extract_ppt_template_structure(template_path)
    return {
        "profile": write_template_profile(profile, output_dir / "template_profile.json"),
        "structure": write_ppt_template_structure(structure, output_dir / "template_structure.json"),
        "structure_markdown": write_ppt_template_structure(structure, output_dir / "template_structure.md"),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = inspect_template(args.template, args.output_dir)
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
