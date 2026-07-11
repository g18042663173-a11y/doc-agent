from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download a Windows/offline wheelhouse for this project.")
    parser.add_argument("--platform", default="win_amd64")
    parser.add_argument("--python-version", default="3.12")
    parser.add_argument("--output", type=Path, default=ROOT / "wheelhouse")
    parser.add_argument("--requirements", type=Path, default=ROOT / "requirements.txt")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(args.output),
        "--platform",
        args.platform,
        "--python-version",
        args.python_version,
        "--only-binary=:all:",
        "-r",
        str(args.requirements),
    ]
    return subprocess.run(command, check=False, encoding="utf-8", errors="replace").returncode


if __name__ == "__main__":
    raise SystemExit(main())
