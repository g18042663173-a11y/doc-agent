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

    assert ".\\start_workbench.ps1" in text
    assert "127.0.0.1:5056" in text
    assert "稳定错误码" in text
    assert "可重试标记" in text
    assert "支持编号" in text
    assert "脱敏失败报告" in text
    assert "backend/app/generators/interface.py" in text
    assert "codeagent.exe" in text
    assert "encoding=\"utf-8\"" in text


def test_generation_notes_cover_analysis_depth_and_intranet_truncation_strategy() -> None:
    notes = (ROOT / "docs" / "GENERATION.md").read_text(encoding="utf-8")
    usage = (ROOT / "docs" / "使用说明.md").read_text(encoding="utf-8")
    intranet = (ROOT / "docs" / "内网接入.md").read_text(encoding="utf-8")

    assert "analysis.json" in notes
    assert "不属于 WordIR、DocumentIR 或 DeckIR" in notes
    assert "每批最多 4 页" in notes
    assert "D001/D002/D006" in notes
    assert "generation_manifest.json" in notes
    assert "scripts/analyze.py" in usage
    assert "--depth 详细" in usage
    assert 'target: "word_ir" | "deck_ir" | "analysis"' in intranet


def test_repository_governance_documents_lock_current_architecture() -> None:
    audit = (ROOT / "REPO_AUDIT.md").read_text(encoding="utf-8")
    architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    refactor_plan = (ROOT / "REFACTOR_PLAN.md").read_text(encoding="utf-8")
    git_workflow = (ROOT / "docs" / "GIT_WORKFLOW.md").read_text(encoding="utf-8")

    assert "backend/app/web_api.py" in audit
    assert "IR 是唯一" in architecture
    assert "experiments/html2pptx" in architecture
    assert "不修改 DeckIR 2.0" in refactor_plan
    assert "短生命周期" in git_workflow

    assert (ROOT / "docs" / "design" / "TECH_REVIEW_DESIGN.md").is_file()
    assert (ROOT / "docs" / "history" / "2026-07" / "AUDIT.md").is_file()
    assert not (ROOT / "backend" / "app" / "web.py").exists()


def test_readme_declares_the_unique_official_entrypoints() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "唯一正式版本与入口" in readme
    assert "根目录 `VERSION`" in readme
    assert "主用户入口" in readme and "DocumentWorkbench.exe" in readme
    assert "python -m app.web_api" in readme
    assert "python -m app.cli.render" in readme
    assert "不包含训练或推理入口" in readme
    assert "experiments/html2pptx" in readme


def test_human_review_doc_describes_current_manual_gates() -> None:
    review = (ROOT / "docs" / "HUMAN_REVIEW.md").read_text(encoding="utf-8")

    assert "DeckIR 2.2" in review
    assert "AssetManifest 1.0" in review
    assert "Windows Credential Manager" in review
    assert "manual_pending" in review
    assert "DeckIR v1.1" not in review
    assert "write placeholder report" not in review
    assert "`[图片占位]`" not in review
    assert "NGA timeout/retry 只写为实现层默认" not in review


def test_version_consolidation_documents_preserve_decision_evidence() -> None:
    audit = (ROOT / "VERSION_CONSOLIDATION_AUDIT.md").read_text(encoding="utf-8")
    report = (ROOT / "VERSION_CONSOLIDATION_REPORT.md").read_text(encoding="utf-8")

    assert "CANONICAL_CANDIDATE" in audit
    assert "FEATURE_DONOR" in audit
    assert "EXPERIMENTAL" in audit
    assert "pre-version-consolidation-20260801" in audit
    assert "唯一正式入口" in report
    assert "验证命令与结果" in report
    assert "恢复方式" in report
    assert "未决事项" in report
    assert "`pending`" not in report
