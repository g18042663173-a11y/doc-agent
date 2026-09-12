"""Run the opt-in Windows Office visual gate without making it a production dependency."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


def _local_module(name: str):
    path = Path(__file__).with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"_local_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Office PNGs, create a contact sheet, and optionally compare a baseline.")
    parser.add_argument("--kind", choices=("deck", "word"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--require-baseline", action="store_true")
    return parser


def build_visual_qa_report(
    export: dict,
    contact_sheet: dict | None,
    *,
    visual_diff: dict | None,
    require_baseline: bool,
) -> dict:
    if not export.get("pass") or (contact_sheet is not None and not contact_sheet.get("pass")):
        return {
            "visual_qa_version": "1.0",
            "status": "failed",
            "pass": False,
            "blocking": True,
            "reason": "office_export_or_contact_sheet_failed",
        }
    if visual_diff is None:
        return {
            "visual_qa_version": "1.0",
            "status": "manual_pending",
            "pass": False,
            "blocking": require_baseline,
            "reason": "approved_visual_baseline_not_provided",
        }
    if not visual_diff.get("pass"):
        return {
            "visual_qa_version": "1.0",
            "status": "failed",
            "pass": False,
            "blocking": True,
            "reason": "visual_diff_threshold_exceeded",
        }
    return {
        "visual_qa_version": "1.0",
        "status": "passed",
        "pass": True,
        "blocking": False,
        "reason": "approved_baseline_matches_candidate",
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    export_script = Path(__file__).with_name("office_visual_export.ps1")
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        raise RuntimeError("PowerShell is unavailable; Windows Office visual QA cannot run")
    command = [
        shell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(export_script),
        "-Kind",
        args.kind,
        "-InputPath",
        str(args.input.resolve()),
        "-OutputDir",
        str(output_dir),
    ]
    export_path = output_dir / "visual_export_report.json"
    # A stale report from a previous run must not masquerade as this run's result
    # when the export script dies before writing it.
    export_path.unlink(missing_ok=True)
    completed = subprocess.run(command, check=False, encoding="utf-8", errors="replace")
    if not export_path.is_file():
        export = {
            "pass": False,
            "reason": f"office export script exited with code {completed.returncode} without writing a report",
        }
    else:
        export = json.loads(export_path.read_text(encoding="utf-8-sig"))
    contact_sheet = None
    visual_diff = None
    if args.kind == "deck" and export.get("pass"):
        png_dir_name = export.get("artifacts", {}).get("png_directory")
        if png_dir_name:
            contact_module = _local_module("contact_sheet")
            contact_sheet = contact_module.create_contact_sheet(
                output_dir / png_dir_name, output_dir / "contact_sheet.png", columns=4
            )
            if args.baseline is not None:
                diff_module = _local_module("visual_diff")
                visual_diff = diff_module.compare_png_sets(
                    args.baseline,
                    output_dir / png_dir_name,
                    pixel_delta=24,
                    max_different_ratio=0.01,
                    max_mean_delta=3.0,
                )
                (output_dir / "visual_diff_report.json").write_text(
                    json.dumps(visual_diff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
    report = build_visual_qa_report(
        export, contact_sheet, visual_diff=visual_diff, require_baseline=args.require_baseline
    )
    report.update(
        {
            "kind": args.kind,
            "input": args.input.name,
            "office_export": export_path.name,
            "contact_sheet": "contact_sheet.png" if contact_sheet else None,
            "visual_diff": "visual_diff_report.json" if visual_diff is not None else None,
        }
    )
    path = output_dir / "visual_qa_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"visual QA report: {path}")
    return 1 if report["blocking"] and not report["pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
