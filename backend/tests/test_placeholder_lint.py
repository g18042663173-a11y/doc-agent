from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_write_placeholder_report(tmp_path: Path) -> None:
    from app.lint.placeholder import write_placeholder_report

    artifact = tmp_path / "artifact.docx"
    artifact.write_text("placeholder", encoding="utf-8")

    report = write_placeholder_report([artifact], tmp_path)
    payload = json.loads(report.read_text(encoding="utf-8"))

    assert payload["summary"]["pass"] is True
    assert payload["items"][0]["code"] == "C0-I01"
