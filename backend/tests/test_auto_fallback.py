from __future__ import annotations

import json
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from app.generators.manager import GeneratorManager
from app.generators.nga import NgaGeneratorError
from app.web_api import create_api_app


@dataclass
class FailingNgaGenerator:
    """An NGA generator that always fails with a retryable error after an
    optional initial success."""

    code: str = "E013"
    retryable: bool = True
    calls: int = 0
    name: str = "nga"

    def generate(self, prompt: str, *, target: str) -> str:
        self.calls += 1
        if prompt.startswith("NGA_CONNECTION_TEST"):
            return '{"ok":true}'
        raise NgaGeneratorError(self.code, "NGA unavailable", retryable=self.retryable)


def _nga_config() -> dict:
    return {
        "config_version": "1.0",
        "base_url": "https://nga.example.internal/v1",
        "endpoint_path": "/chat/completions",
        "model": "model-a",
        "timeout_seconds": 120,
        "max_retries": 2,
        "verify_tls": True,
        "response_format": "json_object",
        "allow_insecure_http": False,
    }


def _manager_with_failing_nga(code: str = "E013") -> GeneratorManager:
    return GeneratorManager(nga_factory=lambda _config, _credential: FailingNgaGenerator(code=code))


def _submit(client, *, generator_payload: dict, target: str = "word") -> dict:
    response = client.put("/api/settings/generator", json=generator_payload)
    assert response.status_code == 200
    response = client.post("/api/settings/generator/test")
    assert response.status_code == 200
    response = client.post("/api/settings/generator/activate")
    assert response.status_code == 200
    response = client.post(
        "/api/generate",
        data={
            "type": target,
            "input_file": (BytesIO(b"# Fallback"), "fallback.md"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 202
    return response.get_json()


def _wait_done(client, job_id: str, *, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = client.get(f"/api/status/{job_id}").get_json()
        if payload["status"] in {"done", "failed", "canceled"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


def _activate_stub(client) -> None:
    response = client.put("/api/settings/generator", json={"generator": "stub"})
    assert response.status_code == 200
    response = client.post("/api/settings/generator/activate")
    assert response.status_code == 200


def test_auto_mode_is_default() -> None:
    manager = GeneratorManager()
    assert manager.snapshot().mode == "auto"
    assert manager.status()["active"]["mode"] == "auto"


def test_strict_mode_can_be_selected() -> None:
    manager = GeneratorManager()
    manager.configure(generator="stub", mode="strict")
    manager.activate()
    assert manager.snapshot().mode == "strict"
    manager.configure(generator="stub", mode="auto")
    manager.activate()
    assert manager.snapshot().mode == "auto"


def test_settings_api_accepts_mode_field(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()
    configured = client.put(
        "/api/settings/generator",
        json={"generator": "stub", "mode": "strict"},
    )
    assert configured.status_code == 200
    assert configured.get_json()["draft"]["mode"] == "strict"
    activated = client.post("/api/settings/generator/activate")
    assert activated.status_code == 200
    assert activated.get_json()["active"]["mode"] == "strict"
    invalid = client.put("/api/settings/generator", json={"generator": "stub", "mode": "unknown"})
    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "E010"


def test_auto_fallback_nga_failure_completes_with_stub(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, generator_manager=_manager_with_failing_nga()).test_client()
    payload = _submit(
        client,
        generator_payload={"generator": "nga", "credential": "secret", "config": _nga_config()},
    )
    done = _wait_done(client, payload["job_id"])

    assert done["status"] == "done"
    assert done["generator"]["name"] == "nga"
    assert done["generator"]["fallback"] is True
    assert done["generator"]["mode"] == "auto"
    # word 目标没有 generation_manifest；fallback 标记记录在 job_state
    state_path = tmp_path / payload["job_id"] / "job_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["generator_fallback"] is True
    assert state["generator_name"] == "nga"


def test_auto_fallback_records_state_file(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, generator_manager=_manager_with_failing_nga()).test_client()
    payload = _submit(
        client,
        generator_payload={"generator": "nga", "credential": "secret", "config": _nga_config()},
    )
    done = _wait_done(client, payload["job_id"])
    assert done["status"] == "done"

    state_path = tmp_path / payload["job_id"] / "job_state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["generator_name"] == "nga"
    assert state["generator_mode"] == "auto"
    assert state["generator_fallback"] is True


def test_strict_mode_nga_failure_fails_job(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, generator_manager=_manager_with_failing_nga()).test_client()
    payload = _submit(
        client,
        generator_payload={"generator": "nga", "credential": "secret", "config": _nga_config(), "mode": "strict"},
    )
    done = _wait_done(client, payload["job_id"])

    assert done["status"] == "failed"
    assert done["generator"]["fallback"] is False
    assert done["generator"]["mode"] == "strict"
    assert done["error"]["code"] == "E013"


def test_auto_fallback_stub_active_has_no_fallback_marker(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()
    _activate_stub(client)
    payload = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Stub active"), "stub.md"),
        },
        content_type="multipart/form-data",
    ).get_json()
    done = _wait_done(client, payload["job_id"])

    assert done["status"] == "done"
    assert done["generator"]["name"] == "stub"
    assert done["generator"]["fallback"] is False


def test_job_state_schema_accepts_fallback_fields(tmp_path: Path) -> None:
    from app.reliability.contracts import JobState

    payload = {
        "job_id": "job-" + "a" * 32,
        "target": "word",
        "depth": None,
        "generator_name": "nga",
        "generator_revision": 3,
        "generator_mode": "auto",
        "generator_fallback": True,
        "status": "done",
        "stage": "done",
        "progress_percent": 100,
        "error": None,
        "artifact_path": "word.docx",
        "report": {},
        "manifest": None,
        "template_path": None,
        "asset_manifest_path": None,
        "assets": {},
        "template_summary": None,
        "idempotency_key": None,
        "created_at": "2026-08-06T00:00:00+00:00",
        "updated_at": "2026-08-06T00:00:00+00:00",
        "expires_at": None,
    }
    model = JobState.model_validate(payload)
    assert model.generator_mode == "auto"
    assert model.generator_fallback is True


def test_auto_fallback_job_payload_has_mode_and_fallback(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, generator_manager=_manager_with_failing_nga()).test_client()
    payload = _submit(
        client,
        generator_payload={"generator": "nga", "credential": "secret", "config": _nga_config()},
    )
    assert payload["generator"]["mode"] == "auto"
    assert payload["generator"]["fallback"] is False  # not yet executed

    done = _wait_done(client, payload["job_id"])
    assert done["generator"]["fallback"] is True
    assert done["generator"]["mode"] == "auto"


def test_auto_fallback_not_triggered_by_stub_failure(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path).test_client()
    _activate_stub(client)

    payload = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Stub failure"), "stub.md"),
        },
        content_type="multipart/form-data",
    ).get_json()
    done = _wait_done(client, payload["job_id"])

    assert done["status"] == "done"
    assert done["generator"]["name"] == "stub"
    assert done["generator"]["fallback"] is False


def test_auto_fallback_deck_manifest_records_generator(tmp_path: Path) -> None:
    client = create_api_app(work_dir=tmp_path, generator_manager=_manager_with_failing_nga()).test_client()
    payload = _submit(
        client,
        generator_payload={"generator": "nga", "credential": "secret", "config": _nga_config()},
        target="deck",
    )
    done = _wait_done(client, payload["job_id"])

    assert done["status"] == "done"
    assert done["generator"]["fallback"] is True
    manifest = done["generation_manifest"]["generator"]
    assert manifest["requested"]["name"] == "nga"
    assert manifest["used"]["name"] == "stub"
    assert manifest["fallback"] is True
    assert manifest["fallback_reason"] == "E013"


def test_stub_generator_success_with_auto_mode_is_not_marked(tmp_path: Path) -> None:
    """Stub success under auto mode must not carry any fallback marker."""
    manager = GeneratorManager(mode="auto")
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()
    payload = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Auto stub"), "auto.md"),
        },
        content_type="multipart/form-data",
    ).get_json()
    done = _wait_done(client, payload["job_id"])

    assert done["status"] == "done"
    assert done["generator"]["name"] == "stub"
    assert done["generator"]["fallback"] is False
