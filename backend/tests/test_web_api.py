from __future__ import annotations

from io import BytesIO
import time
from pathlib import Path

import pytest

from app.web_api import create_api_app


def test_analyze_returns_real_recommendation_for_uploaded_file(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()

    response = client.post(
        "/api/analyze",
        data={"input_file": (BytesIO(b"# Weekly report\n\n- Item one\n- Item two\n"), "weekly.md")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["analysis_version"] == "1.0"
    assert [tier["depth"] for tier in payload["tiers"]] == ["概览", "标准", "详细"]
    assert payload["recommended_depth"] in {"概览", "标准", "详细"}


@pytest.mark.parametrize(
    ("target", "depth", "artifact_name"),
    [("word", None, "word.docx"), ("deck", "概览", "deck.pptx")],
)
def test_generate_status_and_download_complete_stub_artifact(
    tmp_path: Path, target: str, depth: str | None, artifact_name: str
) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()
    data = {
        "type": target,
        "input_file": (BytesIO(b"# Project report\n\n- Completed parser work\n- Next: API review\n"), "report.md"),
    }
    if depth is not None:
        data["depth"] = depth

    created = client.post("/api/generate", data=data, content_type="multipart/form-data")

    assert created.status_code == 202
    job = created.get_json()
    assert job["status"] in {"pending", "running", "done"}
    assert job["type"] == target
    assert job["depth"] == depth

    completed = _wait_for_terminal_status(client, job["job_id"])
    assert completed["status"] == "done", completed
    assert completed["progress"] == {"stage": "done", "percent": 100}
    assert completed["artifact"]["name"] == artifact_name
    assert completed["report"]["summary"]["pass"] is True
    if target == "deck":
        assert completed["generation_manifest"]["depth"] == depth

    download = client.get(completed["artifact"]["download_url"])
    assert download.status_code == 200
    assert download.data[:2] == b"PK"
    assert artifact_name in download.headers["Content-Disposition"]


def test_generate_rejects_missing_upload_and_invalid_deck_options(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()

    missing = client.post("/api/generate", data={"type": "word"})
    assert missing.status_code == 400
    assert missing.get_json()["error"]["code"] == "E001"

    invalid = client.post(
        "/api/generate",
        data={
            "type": "word",
            "depth": "标准",
            "input_file": (BytesIO(b"# Report"), "report.md"),
        },
        content_type="multipart/form-data",
    )
    assert invalid.status_code == 400
    assert "depth" in invalid.get_json()["error"]["message"]


def test_status_and_download_handle_missing_or_unfinished_jobs(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()

    missing = client.get("/api/status/not-found")
    assert missing.status_code == 404

    created = client.post(
        "/api/generate",
        data={
            "type": "deck",
            "depth": "详细",
            "input_file": (BytesIO(b"# Report\n\n- Item\n"), "report.md"),
        },
        content_type="multipart/form-data",
    )
    job_id = created.get_json()["job_id"]
    early_download = client.get(f"/api/download/{job_id}")
    assert early_download.status_code in {200, 409}


def test_generate_records_failed_background_job(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, generator=FailingGenerator()).test_client()

    created = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Report\n\n- Item\n"), "report.md"),
        },
        content_type="multipart/form-data",
    )

    assert created.status_code == 202
    failed = _wait_for_terminal_status(client, created.get_json()["job_id"])
    assert failed["status"] == "failed"
    assert failed["progress"] == {"stage": "failed", "percent": 100}
    assert failed["error"]["code"] == "E001"


class FailingGenerator:
    name = "failing"

    def generate(self, prompt: str, *, target: str) -> str:
        _ = prompt, target
        raise RuntimeError("test generator failure")


def _wait_for_terminal_status(client, job_id: str) -> dict:
    deadline = time.monotonic() + 10
    payload: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/status/{job_id}")
        assert response.status_code == 200
        payload = response.get_json()
        if payload["status"] in {"done", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish: {payload}")
