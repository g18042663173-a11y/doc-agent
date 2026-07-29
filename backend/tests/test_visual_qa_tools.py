from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contact_sheet_is_deterministic_and_labels_each_page(tmp_path: Path) -> None:
    module = _load_script("contact_sheet.py")
    pages = tmp_path / "pages"
    pages.mkdir()
    Image.new("RGB", (160, 90), "#3494BA").save(pages / "Slide1.PNG")
    Image.new("RGB", (160, 90), "#F4B942").save(pages / "Slide2.png")

    report = module.create_contact_sheet(pages, tmp_path / "contact_sheet.png", columns=2)

    assert report["pass"] is True
    assert report["page_count"] == 2
    assert (tmp_path / "contact_sheet.png").is_file()
    assert (tmp_path / "contact_sheet.json").is_file()


def test_visual_qa_never_marks_missing_baseline_as_passed(tmp_path: Path) -> None:
    module = _load_script("ppt_visual_qa.py")
    export = {"pass": True, "artifacts": {"png_directory": "deck-png"}}
    contact = {"pass": True, "page_count": 3}

    pending = module.build_visual_qa_report(export, contact, visual_diff=None, require_baseline=False)
    required = module.build_visual_qa_report(export, contact, visual_diff=None, require_baseline=True)
    approved = module.build_visual_qa_report(export, contact, visual_diff={"pass": True}, require_baseline=True)

    assert pending["status"] == "manual_pending"
    assert pending["pass"] is False
    assert pending["blocking"] is False
    assert required["status"] == "manual_pending"
    assert required["blocking"] is True
    assert approved["status"] == "passed"
    assert approved["pass"] is True
