from __future__ import annotations

import json
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest


ROOT = Path(__file__).resolve().parents[2]


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")


def _word_ir(title: str = "API 验证") -> str:
    return json.dumps(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": title},
            "blocks": [{"type": "paragraph", "text": "真实 API 返回的内容。"}],
        },
        ensure_ascii=False,
    )


def test_codex_generator_posts_responses_request_with_json_only_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generators import codex

    requests = []

    def fake_urlopen(request, *, timeout: int):
        requests.append((request, timeout))
        return FakeResponse({"output_text": _word_ir()})

    monkeypatch.setattr(codex, "urlopen", fake_urlopen)
    generator = codex.CodexGenerator(api_key="test-key", model="claude-test", timeout_seconds=31)

    raw = generator.generate("[完整目标 Schema]\n{}", target="word_ir")

    assert raw == _word_ir()
    request, timeout = requests[0]
    assert request.full_url == "https://opencode.ai/zen/go/v1/responses"
    assert timeout == 31
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["authorization"] == "Bearer test-key"
    # Cloudflare bot protection (HTTP 403 error 1010) rejects Python-urllib UA.
    assert "Python-urllib" not in headers["user-agent"]
    assert headers["user-agent"].startswith("Mozilla/5.0")
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "claude-test"
    assert payload["input"] == "[完整目标 Schema]\n{}"
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["store"] is False
    assert payload["text"] == {"format": {"type": "json_object"}}
    assert "只输出一个完整、合法的 JSON 对象" in payload["instructions"]
    assert "不要使用 Markdown 代码围栏" in payload["instructions"]
    assert "WordIR" in payload["instructions"]


def test_codex_generator_defaults_target_opencode_go_gateway() -> None:
    """B9: the codex adapter defaults must match the verified opencode-go gateway model id."""
    from app.generators import codex

    assert codex.API_BASE_URL == "https://opencode.ai/zen/go/v1"
    assert codex.DEFAULT_MODEL == "deepseek-v4-flash"
    assert codex.DEFAULT_REASONING_EFFORT == "high"
    assert codex.DEFAULT_MAX_TOKENS > 0


def test_codex_generator_chat_completions_payload_carries_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generators import codex

    requests = []

    def fake_urlopen(request, *, timeout: int):
        requests.append((request, timeout))
        return FakeResponse({"choices": [{"message": {"content": _word_ir()}}]})

    monkeypatch.setattr(codex, "urlopen", fake_urlopen)
    generator = codex.CodexGenerator(
        api_key="test-key",
        model="claude-test",
        timeout_seconds=31,
        max_tokens=512,
        api_mode="chat_completions",
    )

    raw = generator.generate("[完整目标 Schema]\n{}", target="word_ir")

    assert raw == _word_ir()
    payload = json.loads(requests[0][0].data.decode("utf-8"))
    assert payload["max_tokens"] == 512
    assert payload["response_format"] == {"type": "json_object"}


def test_codex_generator_adds_deck_content_rules_to_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generators import codex

    observed: dict[str, object] = {}

    def fake_urlopen(request, *, timeout: int):
        observed.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse({"output_text": "{\"ir_type\":\"deck\"}"})

    monkeypatch.setattr(codex, "urlopen", fake_urlopen)
    codex.CodexGenerator(api_key="test-key").generate("prompt", target="deck_ir")

    system = str(observed["instructions"])
    assert "DeckIR" in system
    assert "观点写进标题" in system
    assert "每页最多 3 个内容点" in system
    assert "结论页" in system
    assert "不得自造 Schema 外字段" in system


def test_codex_generator_supports_lightweight_analysis_json_target(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generators import codex

    observed: dict[str, object] = {}

    def fake_urlopen(request, *, timeout: int):
        observed.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse({"output_text": "{}"})

    monkeypatch.setattr(codex, "urlopen", fake_urlopen)
    raw = codex.CodexGenerator(api_key="test-key").generate("analysis prompt", target="analysis")

    assert raw == "{}"
    assert "页数建议" in str(observed["instructions"])
    assert "独立轻量 JSON" in str(observed["instructions"])


def test_codex_generator_requires_environment_key_without_leaking_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generators.codex import CodexConfigurationError, CodexGenerator

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generator = CodexGenerator()

    with pytest.raises(CodexConfigurationError, match="OPENAI_API_KEY") as exc_info:
        generator.generate("prompt", target="word_ir")

    assert "sk-" not in str(exc_info.value)


def test_codex_generator_api_failure_has_no_key_or_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generators import codex

    def fake_urlopen(request, *, timeout: int):
        raise HTTPError(request.full_url, 401, "Unauthorized", hdrs=None, fp=BytesIO(b'{"error":"secret body"}'))

    monkeypatch.setattr(codex, "urlopen", fake_urlopen)
    generator = codex.CodexGenerator(api_key="do-not-leak")

    with pytest.raises(codex.CodexApiError, match="HTTP 401") as exc_info:
        generator.generate("prompt", target="word_ir")

    assert "do-not-leak" not in str(exc_info.value)
    assert "secret body" not in str(exc_info.value)


def test_codex_generator_cli_transport_returns_final_message_without_overriding_active_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.generators import codex

    calls: list[tuple[list[str], dict]] = []

    def fake_run(command: list[str], **kwargs):
        calls.append((command, kwargs))
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(_word_ir("CLI 验证"), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(codex.subprocess, "run", fake_run)
    generator = codex.CodexGenerator(
        transport="cli",
        cli_path="/mock/codex",
        cli_workdir=tmp_path,
        timeout_seconds=45,
    )

    raw = generator.generate("完整 prompt", target="word_ir")

    assert raw == _word_ir("CLI 验证")
    command, kwargs = calls[0]
    assert command[:7] == ["/mock/codex", "exec", "--ephemeral", "--ignore-rules", "-s", "read-only", "-C"]
    assert str(tmp_path) in command
    assert "--model" not in command
    assert kwargs == {
        "input": "完整 prompt",
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "capture_output": True,
        "check": False,
        "timeout": 45,
    }


def test_codex_generator_cli_transport_honors_explicit_model_and_redacts_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.generators import codex

    captured: list[str] = []

    def fake_run(command: list[str], **kwargs):
        captured.extend(command)
        return subprocess.CompletedProcess(command, 1, stdout="provider secret", stderr="sk-do-not-leak")

    monkeypatch.setattr(codex.subprocess, "run", fake_run)
    generator = codex.CodexGenerator(
        transport="cli",
        cli_path="/mock/codex",
        cli_workdir=tmp_path,
        model="gpt-5.5",
    )

    with pytest.raises(codex.CodexApiError, match="Codex CLI generator failed") as exc_info:
        generator.generate("prompt", target="deck_ir")

    assert captured[captured.index("--model") + 1] == "gpt-5.5"
    assert "provider secret" not in str(exc_info.value)
    assert "sk-do-not-leak" not in str(exc_info.value)


def test_codex_generator_cli_transport_reuses_existing_repair_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app.generators import codex
    from app.ir.repair import repair_ir_text

    responses = iter(
        [
            '{"ir_type":"word","ir_version":"1.0","meta":{},"blocks":[]}',
            _word_ir("CLI 修复后"),
        ]
    )

    def fake_run(command: list[str], **kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(next(responses), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(codex.subprocess, "run", fake_run)
    generator = codex.CodexGenerator(transport="cli", cli_path="/mock/codex", cli_workdir=tmp_path)

    result = repair_ir_text(generator.generate("initial", target="word_ir"), target="word_ir", generator=generator)

    assert result.ok
    assert result.value is not None
    assert result.value.meta.title == "CLI 修复后"


def test_codex_generator_reuses_existing_repair_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generators import codex
    from app.ir.repair import repair_ir_text

    responses = iter(
        [
            {"output_text": '{"ir_type":"word","ir_version":"1.0","meta":{},"blocks":[]}'},
            {"output_text": _word_ir("修复后")},
        ]
    )
    prompts: list[str] = []

    def fake_urlopen(request, *, timeout: int):
        prompts.append(json.loads(request.data.decode("utf-8"))["input"])
        return FakeResponse(next(responses))

    monkeypatch.setattr(codex, "urlopen", fake_urlopen)
    generator = codex.CodexGenerator(api_key="test-key")
    first = generator.generate("initial prompt", target="word_ir")
    result = repair_ir_text(first, target="word_ir", generator=generator)

    assert result.ok
    assert result.value is not None
    assert result.value.meta.title == "修复后"
    assert len(prompts) == 2
    assert "E002" in prompts[1]


def test_codex_extract_text_response_rejects_malformed_choices_shapes_with_coded_error() -> None:
    from app.generators.codex import CodexApiError, _extract_text_response

    for malformed in (
        {"choices": [1, 2]},
        {"choices": [{"message": "not a dict"}]},
        {"choices": ["text"]},
    ):
        with pytest.raises(CodexApiError):
            _extract_text_response(malformed, api_mode="chat_completions")


def test_generator_factory_keeps_stub_default_and_allows_explicit_codex(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generators.codex import CodexGenerator
    from app.generators.interface import default_ir_generator, generator_from_name
    from app.generators.stub import StubGenerator

    monkeypatch.delenv("IR_GENERATOR", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # No credentials -> deterministic stub (offline default preserved).
    assert isinstance(default_ir_generator(), StubGenerator)
    assert isinstance(generator_from_name("codex"), CodexGenerator)
    # Credentials present -> real AI generation becomes the default (B9/AI-first).
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert isinstance(default_ir_generator(), CodexGenerator)
    # Explicit IR_GENERATOR override still wins over credentials.
    monkeypatch.setenv("IR_GENERATOR", "stub")
    assert isinstance(default_ir_generator(), StubGenerator)
    monkeypatch.setenv("IR_GENERATOR", "codex")
    assert isinstance(default_ir_generator(), CodexGenerator)
    with pytest.raises(ValueError, match="unsupported IR generator"):
        generator_from_name("unknown")


def test_demo_e2e_uses_existing_repair_loop_for_explicit_codex_generator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import scripts.demo_e2e as demo

    class RepairingCodex:
        name = "codex"

        def __init__(self) -> None:
            self.prompts: list[str] = []

        def generate(self, prompt: str, *, target: str) -> str:
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                return '{"ir_type":"word","ir_version":"1.0","meta":{},"blocks":[]}'
            return _word_ir("修复链路")

    generator = RepairingCodex()
    monkeypatch.setattr(demo, "generator_from_name", lambda name: generator)
    output_dir = tmp_path / "codex-word"

    result = demo.main(
        [
            "samples/input/quarterly_report.md",
            "--target",
            "word",
            "--generator",
            "codex",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    assert len(generator.prompts) == 2
    assert "E002" in generator.prompts[1]
    assert (output_dir / "raw_ir.txt").exists()
    generated = json.loads((output_dir / "word_ir.json").read_text(encoding="utf-8"))
    assert generated["meta"]["title"] == "修复链路"


def test_demo_e2e_codex_without_key_returns_structured_error_without_traceback(tmp_path: Path) -> None:
    env = {key: value for key, value in os.environ.items() if key not in {"OPENAI_API_KEY", "IR_GENERATOR"}}
    env["PYTHONPATH"] = str(ROOT / "backend")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/demo_e2e.py",
            "samples/input/quarterly_report.md",
            "--target",
            "word",
            "--generator",
            "codex",
            "--output-dir",
            str(tmp_path / "missing-key"),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "E001" in result.stderr
    assert "generator" in result.stderr
    assert "Traceback" not in result.stderr
