from __future__ import annotations

from pathlib import Path

from app.ir.deck_ir import DECK_IR_VERSION
from app.web_api import create_api_app


def test_frontend_version_gate_matches_backend_deck_ir_contract(tmp_path: Path) -> None:
    """The browser frontend must require the same DeckIR version the backend reports."""
    client = create_api_app(work_dir=tmp_path).test_client()

    text = client.get("/static/index.html").get_data(as_text=True)
    assert f'version.deck_ir_version !== "{DECK_IR_VERSION}"' in text, (
        "frontend version gate drifted from backend DeckIR contract"
    )

    version = client.get("/api/version").get_json()
    assert version["deck_ir_version"] == DECK_IR_VERSION


def test_web_api_serves_frontend_from_same_origin(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()

    response = client.get("/static/index.html")

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "文档生成工作台" in text
    assert 'sessionFetch("/api/analyze"' in text
    assert 'sessionFetch("/api/generate"' in text
    assert 'fetch("/api/session-token"' in text
    assert "X-Workbench-Session" in text
    assert 'sessionFetch("/api/version"' in text
    assert "api/status" in text
    assert "job.artifact?.download_url" in text
    assert 'data.append("template_file", state.template)' in text
    assert 'data.append("asset_files", file)' in text
    assert 'data-testid="asset-files"' in text
    assert 'data-testid="asset-list"' in text
    assert "模板 Profile" in text
    assert "package-report" in text
    assert "模板结构报告" in text
    assert "替换审计报告" in text
    assert "图片资产清单" in text
    assert "视觉选择审计" in text
    assert 'data-testid="generate-button"' in text
    assert 'data-testid="failure-diagnostic"' in text
    assert 'data-testid="failure-report-link"' in text
    assert "error.payload = data" in text
    assert "finishFailure(error.payload ||" in text
    assert "定位：${error.loc}" in text
    assert 'data-testid="service-status"' in text
    assert 'data-testid="nav-generate"' in text
    assert 'data-testid="nav-tasks"' in text
    assert 'data-testid="nav-settings"' in text
    assert 'data-testid="nav-diagnostics"' in text
    assert 'value="system">跟随系统' in text
    assert 'id="settingsThemeMode"' in text
    assert 'prefers-color-scheme: dark' in text
    assert '--accent: #0078d4;' in text
    assert '--product-mark: #c7000b;' in text
    assert 'sessionFetch("/api/version"' in text
    assert 'data-testid="cancel-job"' in text
    assert 'localStorage.setItem(storageKey' in text
    assert 'Idempotency-Key' in text
    assert '连接中断，正在恢复任务状态' in text
    assert '/api/jobs/${encodeURIComponent(state.jobId)}/cancel' in text
