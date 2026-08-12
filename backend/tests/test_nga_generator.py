from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError

import pytest
from pydantic import ValidationError

from app.generators.nga import (
    MAX_NDJSON_BYTES,
    MAX_RESPONSE_BYTES,
    NgaCliConfig,
    NgaGenerator,
    NgaGeneratorError,
    NgaHttpConfig,
)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        return self.payload if limit < 0 else self.payload[:limit]


def _config(**overrides) -> NgaHttpConfig:
    return NgaHttpConfig(
        base_url="https://nga.example.internal",
        model="internal-model",
        **overrides,
    )


def _response(content: str = '{"ok":true}') -> FakeResponse:
    return FakeResponse(
        json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")
    )


def test_nga_config_rejects_unknown_fields_credentials_in_url_and_unconfirmed_http() -> None:
    with pytest.raises(ValidationError):
        NgaHttpConfig(base_url="https://nga.invalid", model="m", unknown=True)
    with pytest.raises(ValidationError, match="credentials"):
        NgaHttpConfig(base_url="https://user:secret@nga.invalid", model="m")
    with pytest.raises(ValidationError, match="allow_insecure_http"):
        NgaHttpConfig(base_url="http://nga.invalid", model="m")

    allowed = NgaHttpConfig(
        base_url="http://nga.internal",
        model="m",
        allow_insecure_http=True,
    )
    assert allowed.base_url == "http://nga.internal"


def test_nga_generator_sends_openai_compatible_json_without_persisting_token() -> None:
    captured = {}

    def fake_urlopen(request, **kwargs):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["kwargs"] = kwargs
        return _response()

    generator = NgaGenerator(
        config=_config(),
        token="top-secret-token",
        urlopen_fn=fake_urlopen,
    )

    raw = generator.generate("prompt body", target="deck_ir")

    assert raw == '{"ok":true}'
    assert captured["url"] == "https://nga.example.internal/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer top-secret-token"
    assert captured["payload"]["model"] == "internal-model"
    assert captured["payload"]["temperature"] == 0
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["messages"][-1] == {"role": "user", "content": "prompt body"}
    assert "top-secret-token" not in repr(generator)
    assert "top-secret-token" not in generator.config.model_dump_json()


def test_nga_generator_can_disable_response_format_and_use_custom_ca(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ca_bundle = tmp_path / "internal-ca.pem"
    ca_bundle.write_text("certificate", encoding="utf-8")
    captured = {}

    class FakeContext:
        verify_mode = 2

    def fake_context(*, cafile=None):
        captured["cafile"] = cafile
        return FakeContext()

    monkeypatch.setattr("app.generators.nga.ssl.create_default_context", fake_context)

    def fake_urlopen(request, **kwargs):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["context"] = kwargs["context"]
        return _response()

    generator = NgaGenerator(
        config=_config(response_format="none", ca_bundle_path=str(ca_bundle)),
        token="token",
        urlopen_fn=fake_urlopen,
    )

    generator.generate("prompt", target="word_ir")

    assert "response_format" not in captured["payload"]
    assert captured["context"].verify_mode != 0
    assert captured["cafile"] == str(ca_bundle)


def test_nga_generator_retries_only_retryable_failures() -> None:
    attempts = []
    sleeps = []

    def eventually_succeeds(_request, **_kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError("temporary timeout")
        if len(attempts) == 2:
            raise HTTPError("https://nga.invalid", 503, "unavailable", {}, BytesIO())
        return _response()

    generator = NgaGenerator(
        config=_config(max_retries=2),
        token="token",
        urlopen_fn=eventually_succeeds,
        sleep_fn=sleeps.append,
    )

    assert generator.generate("prompt", target="analysis") == '{"ok":true}'
    assert len(attempts) == 3
    assert sleeps == [0.25, 0.5]


def test_nga_generator_does_not_retry_connection_or_tls_failures() -> None:
    attempts = []

    def disconnected(_request, **_kwargs):
        attempts.append(1)
        raise URLError("connection refused")

    generator = NgaGenerator(
        config=_config(max_retries=2),
        token="token",
        urlopen_fn=disconnected,
    )

    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("prompt", target="analysis")

    assert captured.value.code == "E012"
    assert captured.value.retryable is False
    assert len(attempts) == 1


@pytest.mark.parametrize("status", [401, 403])
def test_nga_generator_auth_failure_is_not_retried_or_leaked(status: int) -> None:
    attempts = []

    def unauthorized(_request, **_kwargs):
        attempts.append(1)
        raise HTTPError("https://nga.invalid", status, "secret-token", {}, BytesIO())

    generator = NgaGenerator(
        config=_config(max_retries=2),
        token="secret-token",
        urlopen_fn=unauthorized,
    )

    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("confidential prompt", target="deck_ir")

    assert captured.value.code == "E011"
    assert captured.value.retryable is False
    assert len(attempts) == 1
    assert "secret-token" not in str(captured.value)
    assert "confidential prompt" not in str(captured.value)


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(b"not-json"),
        FakeResponse(b"{}"),
        FakeResponse(json.dumps({"choices": []}).encode("utf-8")),
        FakeResponse(b"x" * (MAX_RESPONSE_BYTES + 1)),
    ],
)
def test_nga_generator_rejects_unreadable_empty_or_oversized_responses(response: FakeResponse) -> None:
    generator = NgaGenerator(
        config=_config(),
        token="token",
        urlopen_fn=lambda *_args, **_kwargs: response,
    )

    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("prompt", target="word_ir")

    assert captured.value.code == "E014"
    assert captured.value.retryable is False


def test_nga_generator_requires_runtime_credential_and_valid_ca_path(tmp_path: Path) -> None:
    without_token = NgaGenerator(config=_config(), token=None)
    with pytest.raises(NgaGeneratorError) as missing:
        without_token.generate("prompt", target="word_ir")
    assert missing.value.code == "E010"
    assert missing.value.retryable is False

    with pytest.raises(NgaGeneratorError) as missing_ca:
        NgaGenerator(
            config=_config(ca_bundle_path=str(tmp_path / "missing.pem")),
            token="token",
        )
    assert missing_ca.value.code == "E010"


# ---------------------------------------------------------------------------
# NGA CLI transport
# ---------------------------------------------------------------------------

def _cli_config(**overrides) -> NgaCliConfig:
    return NgaCliConfig(model="w3/GLM-5.1-WX-Auto", **overrides)


def _fake_cli_run(stdout: str = "", returncode: int = 0):
    import subprocess

    def fake_run(
        command,
        *,
        text,
        encoding,
        errors,
        capture_output,
        check,
        timeout,
    ):
        assert command[:2] == ["nga", "run"]
        assert "--model" in command
        assert "--format" in command
        assert "json" in command
        assert command[-1] == "the prompt"
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr="")

    return fake_run


def test_nga_cli_config_validates_model_and_cli_path() -> None:
    with pytest.raises(ValidationError):
        NgaCliConfig(model="  ")
    with pytest.raises(ValidationError, match="single command"):
        NgaCliConfig(model="m", cli_path="nga\n--bad")

    config = NgaCliConfig(model="w3/GLM-5.1-WX-Auto", cli_path="nga")
    assert config.transport == "cli"
    assert config.timeout_seconds == 300

    # subprocess uses list-form argv (no shell), so spaces in the executable
    # path are safe and must be accepted for typical Windows install locations.
    spaced = NgaCliConfig(model="m", cli_path="C:/Program Files/NGA/nga.exe")
    assert spaced.cli_path == "C:/Program Files/NGA/nga.exe"


def test_nga_cli_transport_concatenates_text_events(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = "\n".join(
        [
            json.dumps({"type": "step_start", "part": {"type": "step-start"}}),
            json.dumps({"type": "text", "part": {"type": "text", "text": '{"title":'}}),
            json.dumps({"type": "tool_use", "part": {"type": "tool", "tool": "bash"}}),
            json.dumps({"type": "text", "part": {"type": "text", "text": '"ok"}'}}),
            json.dumps({"type": "step_finish", "part": {"type": "step-finish", "reason": "stop"}}),
        ]
    )
    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_run_fn=_fake_cli_run(stdout=stream),
    )
    result = generator.generate("the prompt", target="word_ir")
    assert result == '{"title":"ok"}'


def test_nga_cli_transport_works_without_token() -> None:
    generator = NgaGenerator(
        config=_cli_config(),
        token=None,
        subprocess_run_fn=_fake_cli_run(stdout='{"type":"text","part":{"text":"hi"}}'),
    )
    assert generator.generate("the prompt", target="word_ir") == "hi"


def test_nga_cli_transport_retries_retryable_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    calls = {"n": 0}

    def flaky_run(command, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="err")
        return subprocess.CompletedProcess(
            command, 0, stdout='{"type":"text","part":{"text":"ok"}}', stderr=""
        )

    generator = NgaGenerator(
        config=_cli_config(max_retries=2),
        subprocess_run_fn=flaky_run,
        sleep_fn=lambda _seconds: None,
    )
    assert generator.generate("the prompt", target="word_ir") == "ok"
    assert calls["n"] == 3


def test_nga_cli_transport_nonzero_exit_after_retries_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    generator = NgaGenerator(
        config=_cli_config(max_retries=1),
        subprocess_run_fn=_fake_cli_run(returncode=1),
        sleep_fn=lambda _seconds: None,
    )
    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("the prompt", target="word_ir")
    assert captured.value.code == "E013"
    assert captured.value.retryable is True


def test_nga_cli_transport_missing_binary_maps_to_e010(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_run(command, **kwargs):
        raise FileNotFoundError("nga")

    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_run_fn=missing_run,
    )
    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("the prompt", target="word_ir")
    assert captured.value.code == "E010"
    assert captured.value.retryable is False


def test_nga_cli_transport_winerror_206_is_not_reported_as_missing_binary() -> None:
    def overlong_run(command, **kwargs):
        error = FileNotFoundError("The filename or extension is too long")
        error.winerror = 206  # Windows maps WinError 206 to FileNotFoundError
        raise error

    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_run_fn=overlong_run,
    )
    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("the prompt", target="word_ir")
    assert captured.value.code == "E010"
    assert captured.value.retryable is False
    assert "length limit" in str(captured.value)
    assert "not found" not in str(captured.value)


def test_nga_cli_transport_rejects_overlong_prompt_before_spawn_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "win32")

    def must_not_run(command, **kwargs):  # pragma: no cover - guard must fire first
        raise AssertionError("subprocess must not be spawned for an overlong prompt")

    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_run_fn=must_not_run,
    )
    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("x" * 40000, target="deck_ir")
    assert captured.value.code == "E010"
    assert captured.value.retryable is False
    assert "length limit" in str(captured.value)


def test_nga_cli_transport_allows_overlong_prompt_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    long_prompt = "the prompt" + "x" * 40000

    def fake_run(command, **kwargs):
        assert command[-1] == long_prompt
        import subprocess

        return subprocess.CompletedProcess(
            command, 0, stdout='{"type":"text","part":{"text":"ok"}}', stderr=""
        )

    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_run_fn=fake_run,
    )
    assert generator.generate(long_prompt, target="deck_ir") == "ok"


def test_nga_cli_transport_timeout_maps_to_e012_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    def timeout_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_run_fn=timeout_run,
        sleep_fn=lambda _seconds: None,
    )
    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("the prompt", target="word_ir")
    assert captured.value.code == "E012"
    assert captured.value.retryable is True


def test_nga_cli_transport_empty_output_fails_e014() -> None:
    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_run_fn=_fake_cli_run(stdout=""),
    )
    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("the prompt", target="word_ir")
    assert captured.value.code == "E014"


def test_stop_cli_process_kills_whole_tree_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generators import nga as nga_module

    class FakeProcess:
        pid = 4242
        killed = False

        def kill(self) -> None:
            self.killed = True

    process = FakeProcess()
    tree_kill_args: list[list[str]] = []

    def fake_taskkill(command: list[str], **kwargs) -> None:
        tree_kill_args.append(command)

    monkeypatch.setattr(nga_module.os, "name", "nt")
    monkeypatch.setattr(nga_module.subprocess, "run", fake_taskkill)

    nga_module._stop_cli_process(process)

    assert tree_kill_args == [["taskkill", "/T", "/F", "/PID", "4242"]]
    assert process.killed is False


def test_nga_cli_transport_ignores_large_stderr_logs_and_succeeds() -> None:
    class ChattyStderrProcess:
        def __init__(self) -> None:
            self.stdout = BytesIO(b'{"type":"text","part":{"text":"ok"}}')
            self.stderr = BytesIO(b"x" * (MAX_NDJSON_BYTES + 1))
            self.returncode = 0
            self._exit_at = time.monotonic() + 0.4

        def poll(self) -> int | None:
            if time.monotonic() < self._exit_at:
                return None
            return 0

        def kill(self) -> None:
            self.returncode = -9

        def wait(self, timeout: float | None = None) -> int:
            _ = timeout
            return self.returncode

    process = ChattyStderrProcess()

    def fake_popen(command, **kwargs):
        assert kwargs["stderr"] is not None
        return process

    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_popen_fn=fake_popen,
    )

    assert generator.generate("the prompt", target="word_ir") == "ok"


def test_nga_cli_transport_stops_a_stream_that_exceeds_the_output_cap() -> None:
    class BurstingProcess:
        def __init__(self) -> None:
            self.stdout = BytesIO(b"x" * (MAX_NDJSON_BYTES + 1))
            self.stderr = BytesIO()
            self.returncode: int | None = None
            self.killed = False

        def poll(self) -> int | None:
            return self.returncode

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

        def wait(self, timeout: float | None = None) -> int:
            _ = timeout
            return self.returncode or 0

    process = BurstingProcess()

    def fake_popen(command, **kwargs):
        assert command[:2] == ["nga", "run"]
        assert kwargs["stdout"] is not None
        assert kwargs["stderr"] is not None
        return process

    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_popen_fn=fake_popen,
    )

    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("the prompt", target="word_ir")

    assert captured.value.code == "E014"
    assert captured.value.retryable is False
    assert process.killed is True


def test_nga_cli_transport_unreadable_event_fails_e014() -> None:
    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_run_fn=_fake_cli_run(stdout='{"type":"step_start"}\nnot-json\n'),
    )
    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("the prompt", target="word_ir")
    assert captured.value.code == "E014"


def test_nga_cli_transport_no_text_events_fails_e014() -> None:
    generator = NgaGenerator(
        config=_cli_config(),
        subprocess_run_fn=_fake_cli_run(stdout='{"type":"step_start"}\n{"type":"step_finish"}\n'),
    )
    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("the prompt", target="word_ir")
    assert captured.value.code == "E014"


def test_nga_cli_config_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NGA_TRANSPORT", "cli")
    monkeypatch.setenv("NGA_MODEL", "w3/GLM-5.1-WX-Auto")
    generator = NgaGenerator()
    assert generator.transport == "cli"
    assert generator.config is not None
    assert generator.config.model == "w3/GLM-5.1-WX-Auto"
    assert generator.config.cli_path == "nga"
