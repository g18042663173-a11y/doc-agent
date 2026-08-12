from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import os
import time
from pathlib import Path
from threading import Event
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt
from PIL import Image

from app.generators.stub import StubGenerator
import app.web_api as web_api
from app.web_api import create_api_app
from app.version import APP_VERSION
from app.reliability.contracts import FailureEnvelope, JobState


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
    assert not list(tmp_path.glob("analysis-*"))


def test_health_and_version_expose_release_compatibility_without_paths(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()

    version = client.get("/api/version")
    health = client.get("/api/health")

    assert version.status_code == 200
    assert version.get_json() == {
        "service": "huawei-document-generator",
        "app_version": APP_VERSION,
        "api_version": "1.0",
        "deck_ir_version": "2.1",
        "failure_envelope_version": "1.0",
        "job_state_version": "1.0",
    }
    assert health.status_code == 200
    payload = health.get_json()
    assert payload["status"] == "ok"
    assert payload["ready"] is True
    assert payload["runner"]["worker_alive"] is True
    assert payload["runner"]["queue_capacity"] == 4
    assert str(tmp_path) not in health.get_data(as_text=True)


def test_desktop_diagnostics_and_job_list_are_sanitized(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()
    created = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Diagnostic report"), "diagnostic.md"),
        },
        content_type="multipart/form-data",
    )

    diagnostics = client.get("/api/diagnostics")
    jobs = client.get("/api/jobs")

    assert diagnostics.status_code == 200
    payload = diagnostics.get_json()
    assert payload["diagnostics_version"] == "1.0"
    assert payload["application"]["version"] == APP_VERSION
    assert payload["application"]["deck_ir_version"] == "2.0"
    assert payload["generator"]["name"] == "stub"
    assert payload["graphviz"]["source"] in {"bundled", "system", "missing"}
    assert "executable" not in payload["graphviz"]
    assert str(tmp_path) not in diagnostics.get_data(as_text=True)

    assert jobs.status_code == 200
    listed = jobs.get_json()["jobs"]
    assert listed[0]["job_id"] == created.get_json()["job_id"]
    assert "input" not in json.dumps(listed, ensure_ascii=False).lower()


def test_analyze_hard_timeout_frees_request_and_keeps_workspace_for_sweep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class SlowAnalyzeGenerator:
        name = "slow-analyze"

        def generate(self, prompt: str, *, target: str) -> str:
            _ = prompt, target
            time.sleep(30)
            return '{"analysis_version": "1.0"}'

    monkeypatch.setattr(web_api, "ANALYZE_HARD_TIMEOUT_SECONDS", 0.05)
    client = create_api_app(work_dir=tmp_path, generator=SlowAnalyzeGenerator()).test_client()

    started = time.monotonic()
    response = client.post(
        "/api/analyze",
        data={"input_file": (BytesIO(b"# Weekly"), "weekly.md")},
        content_type="multipart/form-data",
    )
    elapsed = time.monotonic() - started

    assert response.status_code == 504
    assert response.get_json()["error"]["code"] == "E012"
    assert elapsed < 5
    assert len(list(tmp_path.glob("analysis-*"))) == 1  # left for the orphan sweep


def test_generator_connection_test_hard_timeout_returns_e012(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.web_api as web_api_module

    class SlowTestManager:
        def snapshot(self) -> dict:
            return {"active": {"name": "nga"}}

        def test_draft(self):
            time.sleep(30)

        def activate(self):
            return {"active": {"name": "nga"}}

    monkeypatch.setattr(web_api_module, "GENERATOR_TEST_TIMEOUT_SECONDS", 0.05)
    client = create_api_app(work_dir=tmp_path, generator_manager=SlowTestManager()).test_client()  # type: ignore[arg-type]

    started = time.monotonic()
    response = client.post("/api/settings/generator/test")
    elapsed = time.monotonic() - started

    assert response.status_code == 504
    assert response.get_json()["error"]["code"] == "E012"
    assert elapsed < 5


def test_analyze_failure_is_sanitized_and_cleans_workspace(tmp_path: Path) -> None:
    client = create_api_app(
        work_dir=tmp_path,
        generator=FailingGenerator("provider_secret=do-not-leak"),
    ).test_client()

    response = client.post(
        "/api/analyze",
        data={"input_file": (BytesIO(b"# Weekly report"), "weekly.md")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 500
    error = FailureEnvelope.model_validate(response.get_json()["error"])
    assert error.code == "E001"
    assert error.stage == "analyzing"
    assert error.retryable is True
    assert "provider_secret" not in response.get_data(as_text=True)
    assert not list(tmp_path.glob("analysis-*"))


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


def test_download_asset_rejects_names_outside_the_fixed_allowlist(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()

    response = client.get("/api/download/not-found/not-allowed")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "E001"


def test_generate_records_failed_background_job(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, generator=FailingGenerator("provider_secret=do-not-leak")).test_client()

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
    assert failed["progress"] == {"stage": "generating", "percent": 100}
    assert failed["error"] == {
        "failure_envelope_version": "1.0",
        "code": "E001",
        "stage": "generating",
        "retryable": True,
        "message": "内容生成服务未完成响应。",
        "suggestion": "请稍后重试；若持续失败，请下载失败报告并提供支持编号。",
        "support_id": failed["error"]["support_id"],
    }
    assert failed["error"]["support_id"].startswith("SUP-")
    assert "provider_secret" not in json.dumps(failed, ensure_ascii=False)
    report_url = failed["assets"]["failure-report"]["download_url"]
    report = client.get(report_url)
    assert report.status_code == 200
    report_payload = report.get_json()
    assert report_payload["error"] == failed["error"]
    assert "provider_secret" not in report.get_data(as_text=True)
    assert client.get(f"/api/download/{failed['job_id']}/lint").status_code == 409


def test_word_job_exposes_lint_report_as_downloadable_asset(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()

    created = client.post(
        "/api/generate",
        data={"type": "word", "input_file": (BytesIO("# Word 报告\n\n- 完成\n- 待办\n".encode("utf-8")), "word.md")},
        content_type="multipart/form-data",
    )
    completed = _wait_for_terminal_status(client, created.get_json()["job_id"])

    assert completed["status"] == "done"
    assert "lint" in completed["assets"]
    report = client.get(completed["assets"]["lint"]["download_url"])
    assert report.status_code == 200
    assert report.get_json()["summary"]["pass"] is not None


def test_generate_deck_with_template_exposes_audit_assets(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path / "jobs").test_client()
    template = _template_bytes(tmp_path)

    created = client.post(
        "/api/generate",
        data={
            "type": "deck",
            "depth": "概览",
            "input_file": (BytesIO(b"# Project report\n\n- Completed\n- Next\n"), "report.md"),
            "template_file": (BytesIO(template), "template.pptx"),
        },
        content_type="multipart/form-data",
    )

    assert created.status_code == 202
    completed = _wait_for_terminal_status(client, created.get_json()["job_id"])
    assert completed["status"] == "done", completed
    assert completed["template"]["mode"] == "template"
    assert set(completed["assets"]) == {
        "lint",
        "package-report",
        "plan",
        "profile",
        "replacement-audit",
        "structure",
        "visual-plan",
        "visual-selection-audit",
        "deck-ir",
    }
    for asset in completed["assets"].values():
        response = client.get(asset["download_url"])
        assert response.status_code == 200
    output = client.get(f"/api/download/{completed['job_id']}/output")
    assert output.status_code == 200
    assert output.data[:2] == b"PK"


def test_generate_deck_accepts_multiple_image_assets_and_exposes_audits(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path / "jobs").test_client()

    def image_bytes(color: tuple[int, int, int]) -> BytesIO:
        stream = BytesIO()
        Image.new("RGB", (320, 180), color).save(stream, format="PNG")
        stream.seek(0)
        return stream

    created = client.post(
        "/api/generate",
        data={
            "type": "deck",
            "depth": "概览",
            "input_file": (BytesIO(b"# Report\n\n- Evidence\n"), "report.md"),
            "asset_files": [(image_bytes((255, 0, 0)), "one.png"), (image_bytes((0, 0, 255)), "two.png")],
        },
        content_type="multipart/form-data",
    )

    assert created.status_code == 202
    completed = _wait_for_terminal_status(client, created.get_json()["job_id"])
    assert completed["status"] == "done", completed
    assert {"asset-manifest", "asset-usage-audit", "visual-plan", "visual-selection-audit"} <= set(completed["assets"])
    manifest = client.get(completed["assets"]["asset-manifest"]["download_url"]).get_json()
    assert len(manifest["assets"]) == 2
    audit = client.get(completed["assets"]["asset-usage-audit"]["download_url"]).get_json()
    assert audit["audit_version"] == "1.0"
    assert audit["usages"]
    visual_plan = client.get(completed["assets"]["visual-plan"]["download_url"]).get_json()
    assert any(item["recommended_layout"] == "image_grid" for item in visual_plan["opportunities"])


def test_generate_word_rejects_image_assets(tmp_path: Path) -> None:
    stream = BytesIO()
    Image.new("RGB", (10, 10), (255, 0, 0)).save(stream, format="PNG")
    stream.seek(0)
    client = create_api_app(work_dir=tmp_path).test_client()
    response = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Report"), "report.md"),
            "asset_files": (stream, "evidence.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "A006"


def test_template_upload_is_deck_only_and_must_be_valid_pptx(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path / "jobs").test_client()
    template = _template_bytes(tmp_path)
    word = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Report"), "report.md"),
            "template_file": (BytesIO(template), "template.pptx"),
        },
        content_type="multipart/form-data",
    )
    corrupt = client.post(
        "/api/generate",
        data={
            "type": "deck",
            "input_file": (BytesIO(b"# Report"), "report.md"),
            "template_file": (BytesIO(b"not a package"), "template.pptx"),
        },
        content_type="multipart/form-data",
    )

    assert word.status_code == 400
    assert "deck" in word.get_json()["error"]["message"]
    assert corrupt.status_code == 400
    assert corrupt.get_json()["error"]["code"] == "E003"


def test_template_ole_error_is_non_retryable_and_actionable(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path / "jobs").test_client()
    response = client.post(
        "/api/generate",
        data={
            "type": "deck",
            "input_file": (BytesIO(b"# Report"), "report.md"),
            "template_file": (BytesIO(_template_with_ole_bytes(tmp_path)), "template.pptx"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "E003"
    assert error["loc"] == "template_file"
    assert error["retryable"] is False
    assert "第 1 页" in error["message"]
    assert "删除" in error["suggestion"] and "PNG" in error["suggestion"]


class FailingGenerator:
    name = "failing"

    def __init__(self, detail: str = "test generator failure") -> None:
        self.detail = detail

    def generate(self, prompt: str, *, target: str) -> str:
        _ = prompt, target
        raise RuntimeError(self.detail)


class TimeoutGenerator:
    name = "timeout"

    def generate(self, prompt: str, *, target: str) -> str:
        _ = prompt, target
        raise TimeoutError("upstream timeout")


class InvalidGenerator:
    name = "invalid"

    def generate(self, prompt: str, *, target: str) -> str:
        _ = prompt, target
        return "raw_model_secret=do-not-leak"


class FailOnceGenerator:
    name = "fail-once"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, *, target: str) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("first call fails")
        return StubGenerator().generate(prompt, target=target)


class SlowGenerator:
    name = "slow"

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    def generate(self, prompt: str, *, target: str) -> str:
        time.sleep(self.seconds)
        return StubGenerator().generate(prompt, target=target)


class BlockingGenerator:
    name = "blocking"

    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def generate(self, prompt: str, *, target: str) -> str:
        self.started.set()
        self.release.wait(timeout=5)
        return StubGenerator().generate(prompt, target=target)


def test_timeout_has_retryable_diagnostic_and_failure_report(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, generator=TimeoutGenerator()).test_client()

    created = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Timeout\n\n- Item\n"), "timeout.md"),
        },
        content_type="multipart/form-data",
    )

    failed = _wait_for_terminal_status(client, created.get_json()["job_id"])
    assert failed["error"]["code"] == "E002"
    assert failed["error"]["stage"] == "generating"
    assert failed["error"]["retryable"] is True
    assert client.get(failed["assets"]["failure-report"]["download_url"]).status_code == 200


def test_invalid_ir_failure_report_never_contains_raw_model_text(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, generator=InvalidGenerator()).test_client()

    created = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Invalid IR\n\n- Item\n"), "invalid.md"),
        },
        content_type="multipart/form-data",
    )

    failed = _wait_for_terminal_status(client, created.get_json()["job_id"])
    assert failed["error"]["code"] == "D001"
    assert "raw_model_secret" not in json.dumps(failed, ensure_ascii=False)
    report = client.get(failed["assets"]["failure-report"]["download_url"])
    assert report.status_code == 200
    assert "raw_model_secret" not in report.get_data(as_text=True)


def test_corrupt_pptx_input_fails_in_parsing_with_a_safe_diagnostic(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()

    created = client.post(
        "/api/generate",
        data={
            "type": "deck",
            "depth": "概览",
            "input_file": (BytesIO(b"not actually a pptx"), "disguised.pptx"),
        },
        content_type="multipart/form-data",
    )

    failed = _wait_for_terminal_status(client, created.get_json()["job_id"])
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "E001"
    assert failed["error"]["stage"] == "parsing"
    assert failed["error"]["retryable"] is False
    assert "not actually a pptx" not in json.dumps(failed, ensure_ascii=False)


def test_content_length_limit_returns_json_envelope_not_html(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()
    client.application.config["MAX_CONTENT_LENGTH"] = 1024

    response = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"x" * 4096), "oversized.md"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert "text/html" not in response.content_type
    assert response.get_json()["error"]["code"] == "E004"
    assert not list(tmp_path.glob("job-*"))


def test_input_upload_limit_is_enforced_before_a_job_is_created(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_api, "MAX_INPUT_UPLOAD_BYTES", 8)
    client = create_api_app(work_dir=tmp_path).test_client()

    response = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"too many bytes"), "large.md"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "E004"
    assert not list(tmp_path.glob("job-*"))


def test_generate_rejects_low_disk_before_creating_workspace(tmp_path: Path, monkeypatch) -> None:
    disk_usage = type("DiskUsage", (), {"total": 100, "used": 100, "free": 0})()
    monkeypatch.setattr(web_api.shutil, "disk_usage", lambda _path: disk_usage)
    client = create_api_app(work_dir=tmp_path).test_client()

    response = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Report"), "report.md"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 507
    error = FailureEnvelope.model_validate(response.get_json()["error"])
    assert error.code == "E004"
    assert error.stage == "request_validation"
    assert error.loc == "work_dir"
    assert error.message == "可用磁盘空间不足，未创建任务。"
    assert error.retryable is True
    assert error.suggestion == "请清理输出目录或释放磁盘空间后重试。"
    assert not list(tmp_path.glob("job-*"))


def test_synchronous_api_errors_follow_failure_envelope_contract(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()

    response = client.post("/api/generate", data={"type": "word"})

    assert response.status_code == 400
    envelope = FailureEnvelope.model_validate(response.get_json()["error"])
    assert envelope.code == "E001"
    assert envelope.stage == "request_validation"
    assert envelope.retryable is False
    assert envelope.support_id.startswith("SUP-")


def test_asset_uploads_enforce_cumulative_size_before_normalization(tmp_path: Path, monkeypatch) -> None:
    def image_stream(color: tuple[int, int, int]) -> BytesIO:
        stream = BytesIO()
        Image.new("RGB", (20, 20), color).save(stream, format="PNG")
        stream.seek(0)
        return stream

    first = image_stream((255, 0, 0))
    second = image_stream((0, 0, 255))
    monkeypatch.setattr(web_api, "MAX_ASSET_UPLOAD_BYTES", 1024)
    monkeypatch.setattr(web_api, "MAX_ASSET_TOTAL_BYTES", len(first.getvalue()) + len(second.getvalue()) - 1)
    client = create_api_app(work_dir=tmp_path).test_client()

    response = client.post(
        "/api/generate",
        data={
            "type": "deck",
            "input_file": (BytesIO(b"# Report"), "report.md"),
            "asset_files": [(first, "one.png"), (second, "two.png")],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "A003"
    assert "总大小" in response.get_json()["error"]["message"]
    assert not list(tmp_path.glob("job-*"))


def test_failure_does_not_pollute_a_later_successful_job(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, generator=FailOnceGenerator()).test_client()
    request_data = {
        "type": "word",
        "input_file": (BytesIO(b"# Isolated report\n\n- Item\n"), "report.md"),
    }

    first = client.post("/api/generate", data=request_data, content_type="multipart/form-data")
    failed = _wait_for_terminal_status(client, first.get_json()["job_id"])
    second = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Isolated report\n\n- Item\n"), "report.md"),
        },
        content_type="multipart/form-data",
    )
    completed = _wait_for_terminal_status(client, second.get_json()["job_id"])

    assert failed["job_id"] != completed["job_id"]
    assert failed["status"] == "failed"
    assert completed["status"] == "done"
    assert "failure-report" not in completed.get("assets", {})
    assert client.get(completed["artifact"]["download_url"]).status_code == 200


def test_completed_job_persists_across_app_restart_and_removes_sensitive_intermediates(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()
    created = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Persistent report\n\n- confidential input"), "report.md"),
        },
        content_type="multipart/form-data",
    )
    completed = _wait_for_terminal_status(client, created.get_json()["job_id"])
    job_dir = tmp_path / completed["job_id"]

    state_path = job_dir / "job_state.json"
    state = JobState.model_validate_json(state_path.read_text(encoding="utf-8"))
    assert state.status == "done"
    assert state.artifact_path == "word.docx"
    assert state.generator_name == "stub"
    assert state.generator_revision == 0
    assert not (job_dir / "input.md").exists()
    assert not (job_dir / "document_ir.json").exists()
    assert not (job_dir / "prompt.txt").exists()
    assert not (job_dir / "raw_ir.txt").exists()
    assert "confidential input" not in state_path.read_text(encoding="utf-8")

    restarted = create_api_app(work_dir=tmp_path).test_client()
    restored = restarted.get(f"/api/status/{completed['job_id']}")
    assert restored.status_code == 200
    assert restored.get_json()["status"] == "done"
    restored_generator = restored.get_json()["generator"]
    assert restored_generator["name"] == "stub"
    assert restored_generator["revision"] == 0
    assert restored_generator["mode"] == "auto"
    assert restored_generator["fallback"] is False
    assert restarted.get(f"/api/download/{completed['job_id']}").status_code == 200


def test_restart_marks_interrupted_job_failed_and_removes_input(tmp_path: Path) -> None:
    job_id = "job-0123456789abcdef0123456789abcdef"
    job_dir = tmp_path / job_id
    job_dir.mkdir()
    (job_dir / "input.md").write_text("secret", encoding="utf-8")
    now = datetime.now(timezone.utc)
    state = JobState(
        job_id=job_id,
        target="word",
        status="running",
        stage="generating",
        progress_percent=40,
        created_at=now,
        updated_at=now,
    )
    (job_dir / "job_state.json").write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")

    client = create_api_app(work_dir=tmp_path).test_client()
    recovered = client.get(f"/api/status/{job_id}").get_json()

    assert recovered["status"] == "failed"
    assert recovered["error"]["code"] == "E015"
    assert recovered["error"]["stage"] == "interrupted"
    assert "failure-report" in recovered["assets"]
    assert not (job_dir / "input.md").exists()


def test_job_timeout_is_terminal_and_late_generator_cannot_overwrite_state(tmp_path: Path) -> None:
    client = create_api_app(
        work_dir=tmp_path,
        generator=SlowGenerator(0.25),
        job_timeout_seconds=0.05,
    ).test_client()
    created = client.post(
        "/api/generate",
        data={"type": "word", "input_file": (BytesIO(b"# Slow"), "slow.md")},
        content_type="multipart/form-data",
    )
    failed = _wait_for_terminal_status(client, created.get_json()["job_id"])

    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "E002"
    assert failed["error"]["stage"] == "timed_out"
    time.sleep(0.35)
    stable = client.get(f"/api/status/{failed['job_id']}").get_json()
    assert stable["status"] == "failed"
    job_dir = tmp_path / failed["job_id"]
    assert not (job_dir / "word.docx").exists()
    assert not (job_dir / "raw_ir.txt").exists()


def test_worker_survives_failure_report_write_error_and_keeps_processing_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _broken_failure_report(job, error):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(web_api, "_write_failure_report", _broken_failure_report)
    client = create_api_app(
        work_dir=tmp_path,
        generator=SlowGenerator(0.25),
        job_timeout_seconds=0.05,
        rate_limit_per_minute=100,
    ).test_client()

    _submit_word_job(client, "first")
    time.sleep(0.3)

    assert client.get("/api/health").get_json()["runner"]["worker_alive"] is True

    second = _submit_word_job(client, "second")
    completed = _wait_for_terminal_status(client, second.get_json()["job_id"])
    assert completed["status"] == "done"
    assert client.get("/api/health").get_json()["runner"]["worker_alive"] is True


def test_cleanup_expired_sweeps_orphaned_analysis_dirs(tmp_path: Path) -> None:
    from datetime import timedelta

    stale = tmp_path / ("analysis-" + "a" * 32)
    stale.mkdir()
    (stale / "junk").write_bytes(b"")
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    os.utime(stale, (old.timestamp(), old.timestamp()))
    fresh = tmp_path / ("analysis-" + "b" * 32)
    fresh.mkdir()
    other = tmp_path / "not-an-analysis"
    other.mkdir()

    client = create_api_app(work_dir=tmp_path).test_client()
    client.get("/api/jobs")  # triggers cleanup_expired

    assert not stale.exists()
    assert fresh.exists()
    assert other.exists()


def test_graphviz_diagnostics_are_cached_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.diagnostics as diagnostics

    calls = {"find": 0, "version": 0}
    monkeypatch.setattr(diagnostics, "_find_graphviz", lambda _root: (calls.__setitem__("find", calls["find"] + 1) or Path("dot"), "system"))
    monkeypatch.setattr(diagnostics, "_read_graphviz_version", lambda _exe: calls.__setitem__("version", calls["version"] + 1) or "12.0")
    monkeypatch.setattr(diagnostics, "_graphviz_cache", None)

    first = diagnostics.graphviz_status()
    second = diagnostics.graphviz_status()

    assert first["version"] == "12.0"
    assert second == first
    assert calls["version"] == 1


def test_browser_mode_rejects_cross_origin_state_changing_requests(tmp_path: Path) -> None:
    browser = create_api_app(work_dir=tmp_path).test_client()
    headers = {"Origin": "https://evil.example"}

    rejected = browser.post(
        "/api/generate",
        headers=headers,
        data={"type": "word", "input_file": (BytesIO(b"# X"), "x.md")},
        content_type="multipart/form-data",
    )
    assert rejected.status_code == 403
    assert rejected.get_json()["error"]["code"] == "E001"
    assert not list(tmp_path.glob("job-*"))

    accepted_loopback = browser.post(
        "/api/generate",
        headers={"Origin": "http://127.0.0.1:5056"},
        data={"type": "word", "input_file": (BytesIO(b"# X"), "x.md")},
        content_type="multipart/form-data",
    )
    assert accepted_loopback.status_code == 202

    accepted_no_origin = browser.post(
        "/api/generate",
        data={"type": "word", "input_file": (BytesIO(b"# Y"), "y.md")},
        content_type="multipart/form-data",
    )
    assert accepted_no_origin.status_code == 202

    read_ok = browser.get("/api/version", headers=headers)
    assert read_ok.status_code == 200

    desktop_ok = create_api_app(
        work_dir=tmp_path / "protected", session_token="desktop-session-secret"
    ).test_client()
    desktop_rejected = desktop_ok.post(
        "/api/generate",
        headers={"Origin": "https://evil.example", "X-Workbench-Session": "desktop-session-secret"},
        data={"type": "word", "input_file": (BytesIO(b"# Z"), "z.md")},
        content_type="multipart/form-data",
    )
    assert desktop_rejected.status_code == 202


def test_idempotency_key_returns_original_job_without_duplicate_directory(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()
    headers = {"Idempotency-Key": "deck-request-0001"}

    first = client.post(
        "/api/generate",
        headers=headers,
        data={"type": "word", "input_file": (BytesIO(b"# Once"), "once.md")},
        content_type="multipart/form-data",
    )
    second = client.post(
        "/api/generate",
        headers=headers,
        data={"type": "word", "input_file": (BytesIO(b"# Duplicate"), "duplicate.md")},
        content_type="multipart/form-data",
    )

    assert first.status_code == 202
    assert second.status_code in {200, 202}
    assert second.get_json()["job_id"] == first.get_json()["job_id"]
    assert len(list(tmp_path.glob("job-*"))) == 1


def test_single_worker_queue_rejects_request_beyond_active_plus_waiting_capacity(tmp_path: Path) -> None:
    generator = BlockingGenerator()
    client = create_api_app(
        work_dir=tmp_path,
        generator=generator,
        queue_capacity=1,
        rate_limit_per_minute=100,
    ).test_client()

    first = _submit_word_job(client, "first")
    assert generator.started.wait(timeout=2)
    second = _submit_word_job(client, "second")
    third = _submit_word_job(client, "third")

    assert first.status_code == 202
    assert second.status_code == 202
    assert third.status_code == 429
    assert third.get_json()["error"]["code"] == "E008"
    generator.release.set()
    assert _wait_for_terminal_status(client, first.get_json()["job_id"])["status"] == "done"
    assert _wait_for_terminal_status(client, second.get_json()["job_id"])["status"] == "done"


def test_running_job_can_be_canceled_and_late_work_is_discarded(tmp_path: Path) -> None:
    generator = BlockingGenerator()
    client = create_api_app(work_dir=tmp_path, generator=generator).test_client()
    created = _submit_word_job(client, "cancel")
    assert generator.started.wait(timeout=2)

    canceled = client.post(f"/api/jobs/{created.get_json()['job_id']}/cancel")

    assert canceled.status_code == 200
    payload = canceled.get_json()
    assert payload["status"] == "canceled"
    assert payload["error"]["code"] == "E009"
    assert "failure-report" in payload["assets"]
    generator.release.set()
    time.sleep(0.2)
    job_dir = tmp_path / payload["job_id"]
    assert not (job_dir / "word.docx").exists()
    assert not (job_dir / "raw_ir.txt").exists()


def test_mutating_api_rate_limit_returns_retryable_failure_envelope(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, rate_limit_per_minute=1).test_client()
    first = client.post(
        "/api/analyze",
        data={"input_file": (BytesIO(b"# First"), "first.md")},
        content_type="multipart/form-data",
    )
    second = client.post(
        "/api/analyze",
        data={"input_file": (BytesIO(b"# Second"), "second.md")},
        content_type="multipart/form-data",
    )

    assert first.status_code == 200
    assert second.status_code == 429
    error = FailureEnvelope.model_validate(second.get_json()["error"])
    assert error.code == "E008"
    assert error.stage == "rate_limited"
    assert error.retryable is True


def test_expired_job_is_removed_on_startup(tmp_path: Path) -> None:
    job_id = "job-fedcba9876543210fedcba9876543210"
    job_dir = tmp_path / job_id
    job_dir.mkdir()
    (job_dir / "word.docx").write_bytes(b"expired")
    now = datetime.now(timezone.utc)
    state = JobState(
        job_id=job_id,
        target="word",
        status="done",
        stage="done",
        progress_percent=100,
        artifact_path="word.docx",
        created_at=now - timedelta(hours=25),
        updated_at=now - timedelta(hours=25),
        expires_at=now - timedelta(hours=1),
    )
    (job_dir / "job_state.json").write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")

    client = create_api_app(work_dir=tmp_path).test_client()

    assert client.get(f"/api/status/{job_id}").status_code == 404
    assert not job_dir.exists()


def _submit_word_job(client, name: str):
    return client.post(
        "/api/generate",
        data={"type": "word", "input_file": (BytesIO(f"# {name}".encode()), f"{name}.md")},
        content_type="multipart/form-data",
    )


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


def _template_bytes(tmp_path: Path) -> bytes:
    path = tmp_path / "api-template.pptx"
    presentation = Presentation()
    cover = presentation.slides.add_slide(presentation.slide_layouts[6])
    _textbox(cover, "TEMPLATE COVER", 1.0, 1.5, 10.0, 1.0, 30)
    _textbox(cover, "TEMPLATE SUBTITLE", 1.0, 2.8, 10.0, 0.7, 18)
    body = presentation.slides.add_slide(presentation.slide_layouts[6])
    _textbox(body, "TEMPLATE TITLE", 0.7, 0.4, 11.0, 0.7, 26)
    _textbox(body, "TEMPLATE BODY WITH ENOUGH CAPACITY", 0.9, 1.5, 11.0, 4.8, 18)
    presentation.save(path)
    return path.read_bytes()


def _template_with_ole_bytes(tmp_path: Path) -> bytes:
    source_bytes = _template_bytes(tmp_path)
    output = BytesIO()
    with ZipFile(BytesIO(source_bytes)) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "ppt/slides/_rels/slide1.xml.rels":
                data = data.replace(
                    b"</Relationships>",
                    b'<Relationship Id="rIdOle" Type="http://schemas.openxmlformats.org/'
                    b'officeDocument/2006/relationships/oleObject" '
                    b'Target="../embeddings/oleObject1.bin"/></Relationships>',
                )
            target.writestr(info, data)
        target.writestr("ppt/embeddings/oleObject1.bin", b"unsafe")
    return output.getvalue()


def _textbox(slide, text: str, left: float, top: float, width: float, height: float, size: float) -> None:
    shape = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    shape.text_frame.text = text
    run = shape.text_frame.paragraphs[0].runs[0]
    run.font.size = Pt(size)
    run.font.name = "Arial"


def test_deck_ir_is_exposed_as_controllable_download_asset(tmp_path) -> None:
    from app.generators.manager import GeneratorManager

    client = create_api_app(work_dir=tmp_path, generator_manager=GeneratorManager()).test_client()
    client.put("/api/settings/generator", json={"generator": "stub"})
    client.post("/api/settings/generator/activate")
    created = client.post(
        "/api/generate",
        data={
            "type": "deck",
            "depth": "概览",
            "input_file": (BytesIO(b"# Deck IR\n\n## A\n\n- 1\n- 2"), "deck.md"),
        },
        content_type="multipart/form-data",
    )
    assert created.status_code == 202
    completed = _wait_for_terminal_status(client, created.get_json()["job_id"])
    assert completed["status"] == "done", completed
    assert "deck-ir" in completed["assets"]
    downloaded = client.get(completed["assets"]["deck-ir"]["download_url"])
    assert downloaded.status_code == 200
    payload = json.loads(downloaded.data.decode("utf-8"))
    assert payload["ir_type"] == "deck"
    assert payload["meta"]["theme"] == "hw_v1"


def test_preflight_rejects_missing_nga_cli_before_queueing(tmp_path) -> None:
    from app.generators.manager import GeneratorManager
    from app.generators.nga import NgaCliConfig, NgaGenerator

    manager = GeneratorManager(
        nga_factory=lambda config, _cred: NgaGenerator(config=config),
    )
    manager.configure(
        generator="nga",
        config=NgaCliConfig(model="m", cli_path="/nonexistent/nga-cli"),
        mode="auto",
    )
    manager._draft.tested = True
    manager.activate()
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()

    response = client.post(
        "/api/generate",
        data={"type": "word", "input_file": (BytesIO(b"# T"), "t.md")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "E010"
    assert response.get_json()["error"]["stage"] == "preflight"


def test_preflight_allows_available_nga_cli(tmp_path, monkeypatch) -> None:
    import subprocess
    from app.generators.manager import GeneratorManager
    from app.generators.nga import NgaCliConfig, NgaGenerator

    fake_cli = tmp_path / "fake-nga"
    fake_cli.write_text("#!/usr/bin/env python3\nprint('{\"type\":\"text\",\"part\":{\"text\":\"ok\"}}')\n", encoding="utf-8")
    fake_cli.chmod(0o755)

    manager = GeneratorManager(
        nga_factory=lambda config, _cred: NgaGenerator(config=config, subprocess_run_fn=lambda *a, **k: subprocess.CompletedProcess(a[0] if a else [], 0, stdout='{"type":"text","part":{"text":"{\\"ok\\":true}"}}', stderr="")),
    )
    manager.configure(
        generator="nga",
        config=NgaCliConfig(model="m", cli_path=str(fake_cli)),
        mode="auto",
    )
    manager._draft.tested = True
    manager.activate()
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()

    response = client.post(
        "/api/generate",
        data={"type": "word", "input_file": (BytesIO(b"# T"), "t.md")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 202


def test_preflight_rejects_deck_via_cli_on_windows(tmp_path, monkeypatch) -> None:
    import subprocess
    from app.generators.manager import GeneratorManager
    from app.generators.nga import NgaCliConfig, NgaGenerator

    monkeypatch.setattr("sys.platform", "win32")
    fake_cli = tmp_path / "fake-nga"
    fake_cli.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    fake_cli.chmod(0o755)

    manager = GeneratorManager(
        nga_factory=lambda config, _cred: NgaGenerator(
            config=config,
            subprocess_run_fn=lambda *a, **k: subprocess.CompletedProcess(
                a[0] if a else [], 0, stdout='{"type":"text","part":{"text":"{\\"ok\\":true}"}}', stderr=""
            ),
        ),
    )
    manager.configure(
        generator="nga",
        config=NgaCliConfig(model="m", cli_path=str(fake_cli)),
        mode="auto",
    )
    manager._draft.tested = True
    manager.activate()
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()

    response = client.post(
        "/api/generate",
        data={"type": "deck", "depth": "概览", "input_file": (BytesIO(b"# T"), "t.md")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    payload = response.get_json()["error"]
    assert payload["code"] == "E010"
    assert payload["stage"] == "preflight"
    assert payload["retryable"] is False


def test_preflight_allows_deck_via_cli_off_windows(tmp_path, monkeypatch) -> None:
    import subprocess
    from app.generators.manager import GeneratorManager
    from app.generators.nga import NgaCliConfig, NgaGenerator

    monkeypatch.setattr("sys.platform", "linux")
    fake_cli = tmp_path / "fake-nga"
    fake_cli.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    fake_cli.chmod(0o755)

    manager = GeneratorManager(
        nga_factory=lambda config, _cred: NgaGenerator(
            config=config,
            subprocess_run_fn=lambda *a, **k: subprocess.CompletedProcess(
                a[0] if a else [], 0, stdout='{"type":"text","part":{"text":"{\\"ok\\":true}"}}', stderr=""
            ),
        ),
    )
    manager.configure(
        generator="nga",
        config=NgaCliConfig(model="m", cli_path=str(fake_cli)),
        mode="auto",
    )
    manager._draft.tested = True
    manager.activate()
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()

    response = client.post(
        "/api/generate",
        data={"type": "deck", "depth": "概览", "input_file": (BytesIO(b"# T"), "t.md")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 202
