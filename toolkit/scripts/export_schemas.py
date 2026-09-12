from __future__ import annotations
# ruff: noqa: E402

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ir.schema_export import export_schemas
from app.assets.contracts import write_asset_schemas
from app.visual.contracts import write_visual_schemas
from app.template.contracts import write_template_schemas
from app.reliability.contracts import write_reliability_schemas


def main() -> int:
    for path in export_schemas(ROOT / "backend" / "schemas", update_history=True):
        print(path.relative_to(ROOT))
    for path in write_template_schemas(ROOT / "backend" / "schemas"):
        print(path.relative_to(ROOT))
    for path in write_asset_schemas(ROOT / "backend" / "schemas"):
        print(path.relative_to(ROOT))
    for path in write_visual_schemas(ROOT / "backend" / "schemas"):
        print(path.relative_to(ROOT))
    for path in write_reliability_schemas(ROOT / "backend" / "schemas"):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
