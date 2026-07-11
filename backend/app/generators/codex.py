from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GeneratorTarget = Literal["word_ir", "deck_ir", "analysis"]
API_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_REASONING_EFFORT = "xhigh"
DEFAULT_TIMEOUT_SECONDS = 300
API_MODES = {"responses", "chat_completions"}
TRANSPORTS = {"http", "cli"}


class CodexGeneratorError(RuntimeError):
    """A non-sensitive failure while invoking the temporary OpenAI-compatible adapter."""


class CodexConfigurationError(CodexGeneratorError):
    """The required local-only API configuration is absent or invalid."""


class CodexApiError(CodexGeneratorError):
    """The API request or response could not be used as raw IR text."""


class CodexGenerator:
    """Temporary OpenAI-compatible adapter for upper-bound IR validation on macOS."""

    name = "codex"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        reasoning_effort: str | None = None,
        api_mode: str | None = None,
        transport: str | None = None,
        cli_path: str | None = None,
        cli_workdir: Path | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        configured_model = model or os.environ.get("OPENAI_MODEL")
        self.model = configured_model or DEFAULT_MODEL
        self._model_is_explicit = configured_model is not None
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or API_BASE_URL).rstrip("/")
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else _integer_environment("OPENAI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
        )
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort or os.environ.get("OPENAI_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT
        self.api_mode = api_mode or os.environ.get("OPENAI_API_MODE") or "responses"
        self.transport = transport or os.environ.get("CODEX_GENERATOR_TRANSPORT") or "http"
        self.cli_path = cli_path or os.environ.get("CODEX_CLI_PATH") or "codex"
        self.cli_workdir = cli_workdir or Path.cwd()
        if not self.model.strip():
            raise CodexConfigurationError("OPENAI_MODEL must not be empty when configuring CodexGenerator.")
        if self.timeout_seconds <= 0:
            raise CodexConfigurationError("CodexGenerator timeout_seconds must be positive.")
        if self.max_tokens <= 0:
            raise CodexConfigurationError("CodexGenerator max_tokens must be positive.")
        if self.api_mode not in API_MODES:
            raise CodexConfigurationError("OPENAI_API_MODE must be responses or chat_completions.")
        if self.transport not in TRANSPORTS:
            raise CodexConfigurationError("CODEX_GENERATOR_TRANSPORT must be http or cli.")

    def generate(self, prompt: str, *, target: GeneratorTarget) -> str:
        if self.transport == "cli":
            return self._generate_cli(prompt)
        return self._generate_http(prompt, target=target)

    def _generate_http(self, prompt: str, *, target: GeneratorTarget) -> str:
        api_key = self._require_api_key()
        request_payload = self._request_payload(prompt, target=target)
        request = Request(
            f"{self.base_url}/{self._endpoint_path()}",
            data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise CodexApiError(f"OpenAI-compatible API request failed with HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise CodexApiError("OpenAI-compatible API request could not be completed.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CodexApiError("OpenAI-compatible API returned an unreadable JSON response.") from exc
        return _extract_text_response(response_payload, api_mode=self.api_mode)

    def _generate_cli(self, prompt: str) -> str:
        """Invoke an already-authenticated Codex CLI without persisting model output or logs."""

        with tempfile.TemporaryDirectory(prefix="codex-generator-") as temporary_dir:
            output_path = Path(temporary_dir) / "last_message.txt"
            command = [
                self.cli_path,
                "exec",
                "--ephemeral",
                "--ignore-rules",
                "-s",
                "read-only",
                "-C",
                str(self.cli_workdir),
                "--output-last-message",
                str(output_path),
            ]
            if self._model_is_explicit:
                command.extend(["--model", self.model])
            command.append("-")
            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                    timeout=self.timeout_seconds,
                )
            except FileNotFoundError as exc:
                raise CodexConfigurationError("Codex CLI was not found; set CODEX_CLI_PATH for cli transport.") from exc
            except subprocess.TimeoutExpired as exc:
                raise CodexApiError("Codex CLI generator timed out.") from exc
            except OSError as exc:
                raise CodexApiError("Codex CLI generator could not be completed.") from exc
            if completed.returncode != 0:
                raise CodexApiError("Codex CLI generator failed.")
            try:
                raw_text = output_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise CodexApiError("Codex CLI generator did not return a readable final message.") from exc
        if not raw_text:
            raise CodexApiError("Codex CLI generator did not return usable text content.")
        return raw_text

    def _require_api_key(self) -> str:
        if not self._api_key:
            raise CodexConfigurationError("OPENAI_API_KEY must be set to use CodexGenerator.")
        return self._api_key

    def _endpoint_path(self) -> str:
        return "responses" if self.api_mode == "responses" else "chat/completions"

    def _request_payload(self, prompt: str, *, target: GeneratorTarget) -> dict[str, Any]:
        system = _system_prompt(target)
        if self.api_mode == "chat_completions":
            return {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "reasoning_effort": self.reasoning_effort,
                "store": False,
            }
        return {
            "model": self.model,
            "instructions": system,
            "input": prompt,
            "max_output_tokens": self.max_tokens,
            "reasoning": {"effort": self.reasoning_effort},
            "store": False,
            "text": {"format": {"type": "json_object"}},
        }


def _extract_text_response(payload: Any, *, api_mode: str) -> str:
    if not isinstance(payload, dict):
        raise CodexApiError("OpenAI-compatible API returned an unexpected response shape.")
    if api_mode == "chat_completions":
        choices = payload.get("choices")
        content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices else None
        text = content.strip() if isinstance(content, str) else ""
    else:
        text = payload.get("output_text", "")
        if not isinstance(text, str):
            text = ""
        if not text:
            output = payload.get("output", [])
            text_parts = [
                content.get("text", "")
                for item in output
                if isinstance(item, dict)
                for content in item.get("content", [])
                if isinstance(content, dict) and content.get("type") == "output_text"
            ]
            text = "".join(part for part in text_parts if isinstance(part, str))
        text = text.strip()
    if not text:
        raise CodexApiError("OpenAI-compatible API response did not include usable text content.")
    return text


def _integer_environment(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise CodexConfigurationError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise CodexConfigurationError(f"{name} must be positive.")
    return value


def _system_prompt(target: GeneratorTarget) -> str:
    target_name = "WordIR" if target == "word_ir" else "DeckIR"
    common = (
        "你是临时 CodexGenerator 验证通道，只负责根据用户消息生成目标 IR 原始文本。\n"
        "只输出一个完整、合法的 JSON 对象；不要输出解释、前言、后记或第二个 JSON。\n"
        "不要使用 Markdown 代码围栏。不得自造 Schema 外字段，必须严格遵守用户消息中给出的完整 Schema、"
        "字段约束、输出预算和合法 few-shot。先在内部检查 JSON 闭合、必填字段、枚举值、数组上限和引用关系。\n"
        "用户消息可能是现有修复回路发来的纠错请求；此时只输出修复后的完整 JSON，不要解释修复过程。\n"
    )
    if target == "analysis":
        return (
            "你负责根据 parser 实测数据给出 PPT 页数建议。只输出用户消息定义的独立轻量 JSON 对象，"
            "不得输出 WordIR、DocumentIR、DeckIR、PPT 内容或解释文字；不得修改用户给出的实测数字。"
        )
    if target == "word_ir":
        return common + (
            f"目标为 {target_name}。保留输入材料的标题层级、关键结论、必要表格和可编辑文本；"
            "不要复制低价值细节，不要编造输入中没有的事实。"
        )
    return common + (
        f"目标为 {target_name}。技术评审稿应让观点写进标题，每页最多 3 个内容点，"
        "对比关系优先用 two_column/table，数值趋势才使用 chart，节点关系才使用 architecture_diagram，"
        "结论页使用 conclusion 收束结论、风险或下一步。关键内容应通过结论式标题和合适布局突出；"
        "当前 IR 没有通用富文本红色/加粗字段，除 table.cell.emphasis 外不得虚构样式字段。"
    )
