from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write an auditable local runtime environment report.")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "environment_report.json")
    return parser


def build_environment_report(repo_root: Path) -> dict[str, object]:
    graphviz_path, graphviz_source = _find_graphviz(repo_root.resolve())
    graphviz: dict[str, object] = {
        "available": graphviz_path is not None,
        "fallback": graphviz_path is None,
        "source": graphviz_source,
        "executable": str(graphviz_path) if graphviz_path is not None else None,
        "version": None,
        "sha256": None,
    }
    if graphviz_path is not None:
        graphviz["version"] = _graphviz_version(graphviz_path)
        graphviz["sha256"] = _sha256(graphviz_path)
    return {
        "report_version": "1.0",
        "python": {
            "executable": sys.executable,
            "version": ".".join(str(value) for value in sys.version_info[:3]),
            "implementation": sys.implementation.name,
            "utf8_mode": bool(sys.flags.utf8_mode),
            "stdout_encoding": sys.stdout.encoding,
        },
        "environment": {
            "PYTHONUTF8": os.environ.get("PYTHONUTF8"),
            "PYTHONIOENCODING": os.environ.get("PYTHONIOENCODING"),
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
        },
        "graphviz": graphviz,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_environment_report(args.repo_root)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"environment report: {output}")
    if report["graphviz"]["fallback"]:  # type: ignore[index]
        print("Graphviz: unavailable; deterministic diagram fallback is active")
    else:
        print(f"Graphviz: {report['graphviz']['executable']}")  # type: ignore[index]
    return 0


def _find_graphviz(repo_root: Path) -> tuple[Path | None, str]:
    bundled = repo_root / "tools" / "graphviz" / "bin" / ("dot.exe" if os.name == "nt" else "dot")
    if bundled.is_file():
        return bundled.resolve(), "bundled"
    resolved = shutil.which("dot.exe") or shutil.which("dot")
    if resolved:
        return Path(resolved).resolve(), "system"
    return None, "missing"


def _graphviz_version(path: Path) -> str:
    result = subprocess.run(
        [str(path), "-V"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return (result.stdout or result.stderr).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
