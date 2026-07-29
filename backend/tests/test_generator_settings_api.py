from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pytest

from app.generators.manager import GeneratorManager
from app.generators.nga import NgaGeneratorError, NgaHttpConfig
from app.generators.stub import StubGenerator
from app.web_api import create_api_app


@dataclass
class LabelGenerator:
    label: str
    name: str = "nga"

    def generate(self, prompt: str, *, target: str) -> str:
        if prompt.startswith("NGA_CONNECTION_TEST"):
            return '{"ok":true}'
        return f"{self.label}:{target}"


def _manager() -> GeneratorManager:
    return GeneratorManager(
        nga_factory=lambda config, _credential: LabelGenerator(config.model),
    )


def _nga_payload(model: str = "model-a", credential: str = "top-secret") -> dict:
    return {
        "generator": "nga",
        "credential": credential,
        "config": {
            "config_version": "1.0",
            "base_url": "https://nga.example.internal/v1",
            "endpoint_path": "/chat/completions",
            "model": model,
            "timeout_seconds": 120,
            "max_retries": 2,
            "verify_tls": True,
            "response_format": "json_object",
            "allow_insecure_http": False,
        },
    }


def test_generator_settings_are_sanitized_and_require_successful_test_before_activation(tmp_path) -> None:
    manager = _manager()
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()

    initial = client.get("/api/settings/generator")
    configured = client.put("/api/settings/generator", json=_nga_payload())
    blocked = client.post("/api/settings/generator/activate")
    tested = client.post("/api/settings/generator/test")
    activated = client.post("/api/settings/generator/activate")

    assert initial.status_code == 200
    assert initial.get_json()["active"]["name"] == "stub"
    assert configured.status_code == 200
    configured_text = configured.get_data(as_text=True)
    assert "top-secret" not in configured_text
    assert configured.get_json()["draft"]["credential_configured"] is True
    assert configured.get_json()["draft"]["tested"] is False
    assert blocked.status_code == 409
    assert blocked.get_json()["error"]["code"] == "E010"
    assert tested.status_code == 200
    assert tested.get_json()["connection"]["ok"] is True
    assert "content" not in tested.get_json()["connection"]
    assert activated.status_code == 200
    assert activated.get_json()["active"]["name"] == "nga"
    assert client.get("/api/health").get_json()["generator"] == "nga"


def test_generator_settings_can_clear_credential_and_switch_back_to_stub(tmp_path) -> None:
    manager = _manager()
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()
    client.put("/api/settings/generator", json=_nga_payload())

    cleared = client.put(
        "/api/settings/generator",
        json={**_nga_payload(credential="replacement"), "credential": None, "clear_credential": True},
    )
    stub = client.put("/api/settings/generator", json={"generator": "stub"})
    activated = client.post("/api/settings/generator/activate")

    assert cleared.status_code == 200
    assert cleared.get_json()["draft"]["credential_configured"] is False
    assert stub.status_code == 200
    assert stub.get_json()["draft"]["tested"] is True
    assert activated.status_code == 200
    assert activated.get_json()["active"]["name"] == "stub"


def test_generator_manager_snapshots_remain_stable_after_later_activation() -> None:
    manager = _manager()
    manager.configure(generator="nga", config=NgaHttpConfig.model_validate(_nga_payload("model-a")["config"]), credential="a")
    manager.test_draft()
    manager.activate()
    first = manager.snapshot()

    manager.configure(generator="nga", config=NgaHttpConfig.model_validate(_nga_payload("model-b")["config"]), credential="b")
    manager.test_draft()
    manager.activate()
    second = manager.snapshot()

    assert first.revision != second.revision
    assert first.generator.generate("job", target="word_ir") == "model-a:word_ir"
    assert second.generator.generate("job", target="word_ir") == "model-b:word_ir"


def test_job_payload_records_the_submitted_generator_snapshot(tmp_path) -> None:
    manager = _manager()
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()

    first = client.post(
        "/api/generate",
        data={"type": "word", "input_file": (BytesIO(b"# Snapshot"), "snapshot.md")},
        content_type="multipart/form-data",
    )
    manager.configure(generator="stub")
    manager.activate()

    assert first.status_code == 202
    assert first.get_json()["generator"] == {"name": "stub", "revision": 0}
    assert manager.snapshot().revision == 1


def test_desktop_session_token_protects_api_without_changing_browser_mode(tmp_path) -> None:
    protected = create_api_app(work_dir=tmp_path / "protected", session_token="desktop-session-secret").test_client()
    browser = create_api_app(work_dir=tmp_path / "browser").test_client()

    rejected = protected.get("/api/version")
    accepted = protected.get(
        "/api/version",
        headers={"X-Workbench-Session": "desktop-session-secret"},
    )

    assert rejected.status_code == 401
    assert rejected.get_json()["error"]["code"] == "E001"
    assert "desktop-session-secret" not in rejected.get_data(as_text=True)
    assert accepted.status_code == 200
    assert browser.get("/api/version").status_code == 200


def test_generator_configuration_rejects_unknown_or_secret_bearing_urls(tmp_path) -> None:
    client = create_api_app(work_dir=tmp_path, generator_manager=_manager()).test_client()

    unknown = client.put("/api/settings/generator", json={"generator": "other"})
    secret_url = client.put(
        "/api/settings/generator",
        json={
            **_nga_payload(),
            "config": {
                **_nga_payload()["config"],
                "base_url": "https://user:password@nga.example.internal",
            },
        },
    )

    assert unknown.status_code == 400
    assert unknown.get_json()["error"]["code"] == "E010"
    assert secret_url.status_code == 400
    assert secret_url.get_json()["error"]["code"] == "E010"
    assert "password" not in secret_url.get_data(as_text=True)


def test_preconfigured_generator_remains_supported_for_existing_api_callers(tmp_path) -> None:
    client = create_api_app(work_dir=tmp_path, generator=StubGenerator()).test_client()
    response = client.post(
        "/api/generate",
        data={
            "type": "word",
            "input_file": (BytesIO(b"# Existing caller"), "existing.md"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 202


def test_connection_test_rejects_non_json_or_unexpected_model_content() -> None:
    @dataclass
    class InvalidConnectionGenerator:
        label: str
        name: str = "nga"

        def generate(self, prompt: str, *, target: str) -> str:
            return self.label

    for content in ("not-json", '{"ok":false}', "{}"):
        manager = GeneratorManager(
            nga_factory=lambda _config, _credential, value=content: InvalidConnectionGenerator(value),
        )
        manager.configure(
            generator="nga",
            config=NgaHttpConfig.model_validate(_nga_payload()["config"]),
            credential="credential",
        )

        with pytest.raises(NgaGeneratorError) as captured:
            manager.test_draft()

        assert captured.value.code == "E014"
