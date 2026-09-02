from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from pptx import Presentation

from app.api import app
from doc_agent.utils.logging_utils import configure_json_logging


def test_user_color_chart_and_smartart_api_routes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    client = TestClient(app)

    created = client.post(
        "/api/users/create",
        json={"user_name": "测试用户", "nga_endpoint": "http://example.test/v1", "auth_token": "secret"},
    )
    assert created.status_code == 200
    user_id = created.json()["user_id"]
    assert created.json()["user"]["auth_token"] == "***HIDDEN***"
    assert "role" not in created.json()["user"]

    listed = client.get("/api/users/list")
    assert listed.status_code == 200
    assert listed.json()["users"][0]["user_id"] == user_id
    assert listed.json()["users"][0]["auth_token"] == "***HIDDEN***"
    assert "role" not in listed.json()["users"][0]

    profile_created = client.post(
        "/api/profiles/create",
        json={
            "user_name": "本地中转站",
            "nga_endpoint": "http://127.0.0.1:8765/v1",
            "auth_token": "EMPTY",
            "llm_provider": "local_relay",
        },
    )
    assert profile_created.status_code == 200
    profile_id = profile_created.json()["profile_id"]
    assert profile_created.json()["user_id"] == profile_id
    assert profile_created.json()["profile"]["profile_id"] == profile_id
    assert profile_created.json()["profile"]["auth_token"] == "***HIDDEN***"

    profiles = client.get("/api/profiles/list")
    assert profiles.status_code == 200
    assert any(profile["profile_id"] == profile_id for profile in profiles.json()["profiles"])

    profile_detail = client.get(f"/api/profiles/{profile_id}")
    assert profile_detail.status_code == 200
    assert profile_detail.json()["profile_id"] == profile_id

    switched = client.post(f"/api/profiles/switch/{profile_id}")
    assert switched.status_code == 200
    assert switched.json()["profile_id"] == profile_id

    colors = client.get("/api/colors/recommend", params={"scenario": "商务报告"})
    assert colors.status_code == 200
    assert colors.json()["recommendations"][0]["scheme_id"] == "business_blue"

    chart = client.post(
        "/api/charts/recommend",
        json={"data_description": "trend by month", "data_characteristics": {"data_type": "time_series", "purpose": "trend"}},
    )
    assert chart.status_code == 200
    assert chart.json()["recommendation"]["chart_type"] == "line"

    smartart = client.post(
        "/api/smartart/generate",
        json={
            "nodes": [{"id": "n1", "text": "开始", "level": 0}],
            "config": {"smartart_type": "process"},
        },
    )
    assert smartart.status_code == 200
    assert smartart.json()["smartart"]["layout"] == "horizontal"


def test_async_generate_api_completes_with_mock_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("PPT_RENDERER", "python_pptx")
    client = TestClient(app)
    profile = client.post(
        "/api/profiles/create",
        json={
            "user_name": "Stub 档案",
            "nga_endpoint": "http://example.test/v1",
            "auth_token": "EMPTY",
            "llm_provider": "stub",
        },
    )
    assert profile.status_code == 200
    profile_id = profile.json()["profile_id"]

    response = client.post(
        "/api/generate/start",
        files={"file": ("input.md", b"# Demo\n\n- Parse\n- Render\n", "text/markdown")},
        data={"target": "pptx", "slides": "5", "color_scheme_id": "business_blue", "profile_id": profile_id},
    )

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    progress = client.get(f"/api/generate/progress/{task_id}")
    assert progress.status_code == 200
    assert progress.json()["status"] == "completed"
    assert progress.json()["metadata"]["original_filename"] == "input.md"
    assert progress.json()["metadata"]["target"] == "pptx"
    assert progress.json()["metadata"]["color_scheme_id"] == "business_blue"
    assert progress.json()["metadata"]["profile_id"] == profile_id
    assert progress.json()["metadata"]["user_id"] == profile_id

    with client.websocket_connect(f"/api/generate/ws/{task_id}") as websocket:
        ws_progress = websocket.receive_json()
    assert ws_progress["task_id"] == task_id
    assert ws_progress["status"] == "completed"
    assert ws_progress["progress"] == 100

    download = client.get(f"/api/generate/download/{task_id}")
    assert download.status_code == 200
    assert download.content

    history = client.get("/api/generate/history")
    assert history.status_code == 200
    assert history.json()["tasks"][0]["task_id"] == task_id

    detail = client.get(f"/api/generate/history/{task_id}")
    assert detail.status_code == 200
    assert detail.json()["metadata"]["slides"] == 5

    deleted = client.delete(f"/api/generate/history/{task_id}")
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True
    assert client.get(f"/api/generate/history/{task_id}").status_code == 404


def test_template_import_returns_style_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    client = TestClient(app)

    source = tmp_path / "template.pptx"
    Presentation().save(str(source))
    imported = client.post(
        "/api/templates/import",
        files={"file": ("template.pptx", source.read_bytes(), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        data={"name": "Style Template", "category": "business"},
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["style_summary"]["mode"] == "style_apply"
    assert body["style_summary"]["master_count"] >= 1

    listed = client.get("/api/templates/list")
    assert listed.status_code == 200
    custom = [item for item in listed.json()["templates"] if item["template_id"] == body["template_id"]][0]
    assert custom["style_summary"]["slide_size"]["width_inches"] > 0


def test_system_config_metrics_and_request_logging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    configure_json_logging(log_dir=tmp_path / "logs")
    client = TestClient(app)

    health = client.get("/api/system/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.headers["X-Request-ID"]

    imported = client.post(
        "/api/config/import",
        json={
            "users": [
                {
                    "user_name": "导入用户",
                    "nga_endpoint": "http://example.test/v1",
                    "auth_token": "plain-token",
                }
            ],
            "color_schemes": [
                {
                    "scheme_id": "imported_scheme",
                    "name": "导入配色",
                    "category": "business",
                    "primary_color": "#123456",
                    "secondary_color": "#234567",
                    "accent_color": "#345678",
                    "background_color": "#FFFFFF",
                    "text_color": "#111111",
                }
            ],
            "templates": [
                {
                    "template_id": "imported_template",
                    "name": "导入模板",
                    "category": "business",
                    "description": "Restored template metadata",
                    "file_path": str(tmp_path / "data" / "templates" / "custom" / "imported_template.pptx"),
                    "layout_config": {
                        "layout_id": "restored_layout",
                        "name": "Restored Layout",
                        "description": "Imported from backup",
                        "slide_masters": ["slide_master_0"],
                        "default_layouts": {},
                    },
                    "font_config": {"zh": "Microsoft YaHei", "en": "Arial"},
                    "custom_settings": {
                        "analysis": {
                            "mode": "style_apply",
                            "slide_size": {"width_inches": 13.333, "height_inches": 7.5},
                            "colors": {"primary": "123456"},
                        }
                    },
                    "is_system": False,
                }
            ],
        },
    )
    assert imported.status_code == 200
    assert imported.json()["imported_users"] == 1
    assert imported.json()["imported_templates"] == 1
    assert imported.json()["imported_color_schemes"] == 1

    exported = client.get("/api/config/export")
    assert exported.status_code == 200
    body = exported.json()
    assert body["settings"]["llm_api_key"] == "***HIDDEN***"
    assert body["users"][0]["auth_token"] == "***HIDDEN***"
    assert any(template["template_id"] == "imported_template" for template in body["templates"])
    assert any(scheme["scheme_id"] == "imported_scheme" for scheme in body["color_schemes"])

    metrics = client.get("/api/system/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["app"]["total_requests"] >= 4
    assert metrics.json()["storage"]["data_dir_exists"] is True

    log_file = tmp_path / "logs" / "app.log"
    assert log_file.exists()
    assert "request completed" in log_file.read_text(encoding="utf-8")
