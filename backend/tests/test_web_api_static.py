from __future__ import annotations

from pathlib import Path

from app.web_api import create_api_app


def test_web_api_serves_frontend_from_same_origin(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()

    response = client.get("/static/index.html")

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "文档生成工作台" in text
    assert 'fetch("/api/analyze"' in text
    assert 'fetch("/api/generate"' in text
    assert "api/status" in text
    assert "job.artifact?.download_url" in text
