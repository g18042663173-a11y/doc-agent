from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from pydantic import ValidationError

from app.generators.nga import (
    MAX_RESPONSE_BYTES,
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
