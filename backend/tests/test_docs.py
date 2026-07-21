from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_yellow_zone_integration_doc_covers_required_topics() -> None:
    text = (ROOT / "docs" / "内网接入.md").read_text(encoding="utf-8")

    assert "generators/nga.py" in text
    assert "华为官方渲染 Skill" in text
    assert "NGA_BASE_URL" in text
    assert "NGA_TOKEN" in text
    assert "wheelhouse" in text
    assert "stub 全链路" in text
    assert "不动清单" in text


def test_delivery_docs_and_demo_script_exist() -> None:
    usage = (ROOT / "docs" / "使用说明.md").read_text(encoding="utf-8")
    acceptance = (ROOT / "docs" / "验收手册.md").read_text(encoding="utf-8")
    record_script = (ROOT / "scripts" / "record_demo.sh").read_text(encoding="utf-8")
    verify_ps1 = (ROOT / "verify.ps1").read_text(encoding="utf-8")

    assert "app.cli.parse" in usage
    assert "app.cli.render --type deck" in usage
    assert "python scripts/verify.py" in acceptance
    assert ".\\verify.ps1" in acceptance
    assert "record_demo.py" in record_script
    assert "python scripts/verify.py" in verify_ps1


def test_usage_documents_document_ir_v10_compatibility() -> None:
    usage = (ROOT / "docs" / "使用说明.md").read_text(encoding="utf-8")

    assert "DocumentIR 1.0 兼容读取" in usage
    assert "在内存中把版本迁移为 1.2" in usage
    assert "重新执行 1.2" in usage
    assert "不会覆写原文件" in usage


def test_web_usage_doc_covers_stub_and_nga_switch() -> None:
    text = (ROOT / "docs" / "界面使用说明.md").read_text(encoding="utf-8")

    assert "PYTHONPATH=backend python3 -m app.web" in text
    assert "Error / Warning / Info" in text
    assert "backend/app/generators/interface.py" in text
    assert "codeagent.exe" in text
    assert "encoding=\"utf-8\"" in text


def test_generation_notes_cover_analysis_depth_and_intranet_truncation_strategy() -> None:
    notes = (ROOT / "GENERATION_NOTES.md").read_text(encoding="utf-8")
    usage = (ROOT / "docs" / "使用说明.md").read_text(encoding="utf-8")
    intranet = (ROOT / "docs" / "内网接入.md").read_text(encoding="utf-8")

    assert "analysis.json" in notes
    assert "不属于\nWordIR、DocumentIR 或 DeckIR" in notes
    assert "每批\n最多 4 页" in notes
    assert "D001/D002/D006" in notes
    assert "generation_manifest.json" in notes
    assert "scripts/analyze.py" in usage
    assert "--depth 详细" in usage
    assert 'target: "word_ir" | "deck_ir" | "analysis"' in intranet
