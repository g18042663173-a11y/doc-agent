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


def test_desktop_payload_with_transport_and_cli_path_fields_can_save_http_config(tmp_path) -> None:
    manager = _manager()
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()

    payload = {
        **_nga_payload(),
        "config": {
            **_nga_payload()["config"],
            "transport": "http",
            "cli_path": "nga",
        },
    }
    configured = client.put("/api/settings/generator", json=payload)
    assert configured.status_code == 200
    assert configured.get_json()["draft"]["config"]["base_url"] == "https://nga.example.internal/v1"
    assert "cli_path" not in configured.get_json()["draft"]["config"]
    assert "top-secret" not in configured.get_data(as_text=True)


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
    generator_payload = first.get_json()["generator"]
    assert generator_payload["name"] == "stub"
    assert generator_payload["revision"] == 0
    assert generator_payload["mode"] == "auto"
    assert generator_payload["fallback"] is False
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


def test_cli_transport_config_can_be_saved_tested_and_activated(tmp_path) -> None:
    from app.generators.nga import NgaCliConfig

    @dataclass
    class CliLabelGenerator:
        label: str
        name: str = "nga"

        def generate(self, prompt: str, *, target: str) -> str:
            if prompt.startswith("NGA_CONNECTION_TEST"):
                return '{"ok":true}'
            return f"{self.label}:{target}"

    manager = GeneratorManager(
        nga_factory=lambda config, _credential: CliLabelGenerator(
            config.model if isinstance(config, NgaCliConfig) else str(config)
        ),
    )
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()

    payload = {
        "generator": "nga",
        "credential": None,
        "config": {
            "config_version": "1.0",
            "transport": "cli",
            "model": "w3/GLM-5.1-WX-Auto",
            "cli_path": "nga",
            "timeout_seconds": 300,
            "max_retries": 2,
        },
    }
    configured = client.put("/api/settings/generator", json=payload)
    assert configured.status_code == 200
    assert configured.get_json()["draft"]["config"]["transport"] == "cli"
    assert configured.get_json()["draft"]["credential_configured"] is False

    tested = client.post("/api/settings/generator/test")
    assert tested.status_code == 200
    assert tested.get_json()["connection"]["ok"] is True

    activated = client.post("/api/settings/generator/activate")
    assert activated.status_code == 200
    assert activated.get_json()["active"]["name"] == "nga"
    assert activated.get_json()["active"]["config"]["transport"] == "cli"


@dataclass
class CodexLabelGenerator:
    config: object
    name: str = "codex"
    _api_key: str | None = None

    def generate(self, prompt: str, *, target: str) -> str:
        if prompt.startswith("NGA_CONNECTION_TEST"):
            return '{"ok":true}'
        return f"codex:{getattr(self.config, 'model', '?' )}:{target}"


def test_codex_settings_can_be_configured_tested_and_activated(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    manager = GeneratorManager(
        codex_factory=lambda config, credential: CodexLabelGenerator(config, _api_key=credential)
    )
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()

    payload = {
        "generator": "codex",
        "credential": "sk-secret-123",
        "config": {
            "config_version": "1.0",
            "base_url": "https://opencode.ai/zen/go/v1",
            "model": "deepseek-v4-flash",
            "api_mode": "responses",
            "timeout_seconds": 120,
            "reasoning_effort": "high",
        },
    }
    configured = client.put("/api/settings/generator", json=payload)
    assert configured.status_code == 200
    configured_text = configured.get_data(as_text=True)
    assert "sk-secret-123" not in configured_text
    draft = configured.get_json()["draft"]
    assert draft["name"] == "codex"
    assert draft["credential_configured"] is True
    assert draft["tested"] is False
    assert draft["config"]["base_url"] == "https://opencode.ai/zen/go/v1"
    assert draft["config"]["model"] == "deepseek-v4-flash"
    assert draft["config"]["api_mode"] == "responses"

    blocked = client.post("/api/settings/generator/activate")
    assert blocked.status_code == 409
    assert blocked.get_json()["error"]["code"] == "E010"

    tested = client.post("/api/settings/generator/test")
    assert tested.status_code == 200
    assert tested.get_json()["connection"]["ok"] is True

    activated = client.post("/api/settings/generator/activate")
    assert activated.status_code == 200
    activated_text = activated.get_data(as_text=True)
    assert "sk-secret-123" not in activated_text
    active = activated.get_json()["active"]
    assert active["name"] == "codex"
    assert active["credential_configured"] is True
    assert active["config"]["model"] == "deepseek-v4-flash"
    assert active["config"]["base_url"] == "https://opencode.ai/zen/go/v1"
    assert client.get("/api/health").get_json()["generator"] == "codex"


def test_codex_initial_from_environment_prefills_draft_and_reports_credential_state(
    tmp_path, monkeypatch
) -> None:
    from app.generators.codex import CodexGenerator

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
    manager = GeneratorManager(initial_generator=CodexGenerator())
    client = create_api_app(work_dir=tmp_path, generator_manager=manager).test_client()

    status = client.get("/api/settings/generator").get_json()
    active = status["active"]
    assert active["name"] == "codex"
    assert active["credential_configured"] is True
    assert active["config"]["base_url"] == "https://opencode.ai/zen/go/v1"
    assert active["config"]["model"] == "deepseek-v4-flash"
    # The draft is pre-filled from the active codex instance so the settings
    # form can show and edit the endpoint/model without re-typing them.
    assert status["draft"]["name"] == "codex"
    assert status["draft"]["config"]["model"] == "deepseek-v4-flash"
    assert "sk-env-key" not in status
    assert "sk-env-key" not in client.get("/api/settings/generator").get_data(as_text=True)

    monkeypatch.delenv("OPENAI_API_KEY")
    # A freshly constructed generator without a credential reports the env state.
    fresh = GeneratorManager(initial_generator=CodexGenerator())
    fresh_client = create_api_app(work_dir=tmp_path, generator_manager=fresh).test_client()
    assert fresh_client.get("/api/settings/generator").get_json()["active"]["credential_configured"] is False
