from io import BytesIO
import time

import pytest

from app.web_api import create_api_app


@pytest.mark.parametrize("target", ["word", "deck"])
def test_every_advertised_asset_survives_success_cleanup_and_downloads(tmp_path, target):
    app = create_api_app(work_dir=tmp_path)
    client = app.test_client()
    created = client.post("/api/generate", data={"type": target,
        "input_file": (BytesIO(b"# Progress report\n\n- Analysis complete\n- Next: verification\n"), "material.md")},
        content_type="multipart/form-data")
    assert created.status_code == 202
    job_id = created.get_json()["job_id"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        payload = client.get(f"/api/status/{job_id}").get_json()
        if payload["status"] in {"done", "failed", "canceled"}:
            break
        time.sleep(0.02)
    assert payload["status"] == "done", payload
    assert "deck-ir" not in payload.get("assets", {})
    # Completion cleanup runs just after publishing terminal state.
    job = app.config["API_JOBS"].get(job_id)
    for _ in range(100):
        if not (job.work_dir / "deck_ir.json").exists():
            break
        time.sleep(0.02)
    payload = client.get(f"/api/status/{job_id}").get_json()
    assert "deck-ir" not in payload.get("assets", {})
    assert "original-input" not in payload.get("assets", {})
    assert not (job.work_dir / "deck_ir.json").exists()
    for asset in payload.get("assets", {}).values():
        response = client.get(asset["download_url"])
        assert response.status_code == 200, asset
    # Persisted state must not resurrect the cleared download links.
    restored = create_api_app(work_dir=tmp_path).test_client()
    payload = restored.get(f"/api/status/{job_id}").get_json()
    for asset in payload.get("assets", {}).values():
        assert restored.get(asset["download_url"]).status_code == 200
