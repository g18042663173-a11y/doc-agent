from __future__ import annotations

import json
from pathlib import Path


def write_placeholder_report(rendered_files: list[Path], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "summary": {"errors": 0, "warnings": 0, "infos": len(rendered_files), "pass": True},
        "items": [
            {
                "code": "C0-I01",
                "level": "Info",
                "message": f"Placeholder render produced {path.name}",
            }
            for path in rendered_files
        ],
    }
    report_path = output_dir / "c0_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path
