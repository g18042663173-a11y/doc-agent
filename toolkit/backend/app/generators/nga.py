from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import socket
import ssl
import subprocess
import sys
from threading import Event, Thread
import time
from typing import Any, Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.generators.interface import GeneratorCanceled


GeneratorTarget = Literal["word_ir", "deck_ir", "analysis"]
ResponseFormat = Literal["json_object", "none"]
NgaTransport = Literal["http", "cli"]
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_NDJSON_BYTES = 10 * 1024 * 1024
RETRYABLE_HTTP_STATUSES = frozenset({429, 502, 503, 504})

# Windows CreateProcess rejects command lines longer than 32767 UTF-16
# characters; CPython surfaces that as FileNotFoundError with winerror 206.
# A deck prompt (~58 KB, DeckIR schema alone ~52 KB) always exceeds it, so the
# CLI transport must fail honestly instead of misreporting a missing binary.
_WINDOWS_COMMAND_LINE_LIMIT = 32767
_WINERROR_FILENAME_TOO_LONG = 206
_CLI_STREAM_CHUNK_BYTES = 64 * 1024


class _CliOutputLimitExceeded(Exception):
    pass


class NgaHttpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_version: Literal["1.0"] = "1.0"
    base_url: str = Field(min_length=1, max_length=2048)
    endpoint_path: str = Field(default="/v1/chat/completions", min_length=1, max_length=512)
    model: str = Field(min_length=1, max_length=256)
    timeout_seconds: int = Field(default=120, ge=1, le=900)
    max_retries: int = Field(default=2, ge=0, le=5)
    verify_tls: bool = True
    ca_bundle_path: str | None = Field(default=None, min_length=1, max_length=1024)
    response_format: ResponseFormat = "json_object"
    allow_insecure_http: bool = False

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password:
            raise ValueError("base_url must not contain credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("base_url must not contain query or fragment components")
        return normalized

    @field_validator("endpoint_path")
    @classmethod
    def validate_endpoint_path(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if not normalized.startswith("/") or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("endpoint_path must be an absolute URL path")
        if ".." in Path(normalized).parts:
            raise ValueError("endpoint_path must not contain parent traversal")
        return normalized

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_transport_security(self) -> NgaHttpConfig:
        if self.base_url.startswith("http://") and not self.allow_insecure_http:
            raise ValueError("HTTP requires allow_insecure_http=true")
        if self.ca_bundle_path and not self.verify_tls:
            raise ValueError("ca_bundle_path cannot be used when verify_tls=false")
        return self


class NgaCliConfig(BaseModel):
    """Configuration for NGA CLI transport (local `nga run` command)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    config_version: Literal["1.0"] = "1.0"
    transport: Literal["cli"] = "cli"
    model: str = Field(min_length=1, max_length=256)
    cli_path: str = Field(default="nga", min_length=1, max_length=1024)
    timeout_seconds: int = Field(default=300, ge=1, le=900)
    max_retries: int = Field(default=2, ge=0, le=5)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model must not be blank")
        return normalized

    @field_validator("cli_path")
    @classmethod
    def validate_cli_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or "\n" in normalized or "\r" in normalized:
            raise ValueError("cli_path must be a single command name or executable path")
        return normalized


class NgaGeneratorError(RuntimeError):
    """Sanitized NGA failure suitable for stable API error mapping."""

    def __init__(
        self,
        code: Literal["E010", "E011", "E012", "E013", "E014"],
        message: str,
        *,
        retryable: bool,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.http_status = http_status


class NgaGenerator:
    name = "nga"

    def __init__(
        self,
        *,
        config: NgaHttpConfig | NgaCliConfig | None = None,
        token: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
        urlopen_fn: Callable[..., Any] = urlopen,
        sleep_fn: Callable[[float], None] = time.sleep,
        subprocess_run_fn: Callable[..., Any] | None = None,
        subprocess_popen_fn: Callable[..., Any] | None = None,
    ) -> None:
        if config is None:
            transport = os.environ.get("NGA_TRANSPORT", "http")
            environment_model = model or os.environ.get("NGA_MODEL")
            if transport == "cli":
                if not environment_model:
                    self.config = None
                else:
                    self.config = NgaCliConfig(
                        model=environment_model,
                        cli_path=os.environ.get("NGA_CLI_PATH", "nga"),
                        timeout_seconds=timeout_seconds or _environment_integer("NGA_TIMEOUT_SECONDS", 300),
                        max_retries=_environment_integer("NGA_MAX_RETRIES", 2),
                    )
            else:
                environment_base_url = base_url or os.environ.get("NGA_BASE_URL")
                if not environment_base_url or not environment_model:
                    self.config = None
                else:
                    self.config = NgaHttpConfig(
                        base_url=environment_base_url,
                        endpoint_path=os.environ.get("NGA_ENDPOINT_PATH", "/v1/chat/completions"),
                        model=environment_model,
                        timeout_seconds=timeout_seconds or _environment_integer("NGA_TIMEOUT_SECONDS", 120),
                        max_retries=_environment_integer("NGA_MAX_RETRIES", 2),
                        verify_tls=_environment_boolean("NGA_VERIFY_TLS", True),
                        ca_bundle_path=os.environ.get("NGA_CA_BUNDLE") or None,
                        response_format=os.environ.get("NGA_RESPONSE_FORMAT", "json_object"),
                        allow_insecure_http=_environment_boolean("NGA_ALLOW_INSECURE_HTTP", False),
                    )
        else:
            self.config = config
        self._token = token if token is not None else os.environ.get("NGA_TOKEN")
        self._urlopen = urlopen_fn
        self._sleep = sleep_fn
        self._subprocess_run = subprocess_run_fn
        self._subprocess_popen = subprocess_popen_fn or subprocess.Popen
        self._ssl_context = self._build_ssl_context()

    @property
    def transport(self) -> NgaTransport:
        return "cli" if isinstance(self.config, NgaCliConfig) else "http"

    def __repr__(self) -> str:
        model = self.config.model if self.config is not None else "<unconfigured>"
        return (
            f"NgaGenerator(model={model!r}, transport={self.transport}, "
            f"credential_configured={bool(self._token)})"
        )

    def generate(
        self,
        prompt: str,
        *,
        target: GeneratorTarget,
        cancel_event: Event | None = None,
    ) -> str:
        if self.config is None:
            raise NgaGeneratorError(
                "E010",
                "NGA configuration is incomplete.",
                retryable=False,
            )
        if self.transport == "http" and not self._token:
            raise NgaGeneratorError(
                "E010",
                "NGA runtime credential is not configured.",
                retryable=False,
            )

        for attempt in range(self.config.max_retries + 1):
            if cancel_event is not None and cancel_event.is_set():
                raise GeneratorCanceled("NGA generator canceled")
            try:
                if self.transport == "cli":
                    return self._send_cli(prompt, cancel_event=cancel_event)
                return self._send_http(prompt, target=target, cancel_event=cancel_event)
            except NgaGeneratorError as exc:
                if not exc.retryable or attempt >= self.config.max_retries:
                    raise
                self._sleep(min(0.25 * (2**attempt), 2.0))
        raise AssertionError("NGA retry loop did not return or raise")

    def _send_http(self, prompt: str, *, target: GeneratorTarget, cancel_event: Event | None = None) -> str:
        assert isinstance(self.config, NgaHttpConfig)
        request = self._request(prompt, target=target)
        if cancel_event is None:
            raw = self._http_call(request)
        else:
            raw = self._http_call_cancellable(request, cancel_event)
            if raw is None:
                raise GeneratorCanceled("NGA HTTP request canceled")

        if len(raw) > MAX_RESPONSE_BYTES:
            raise NgaGeneratorError(
                "E014",
                "NGA response exceeded the allowed size.",
                retryable=False,
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise NgaGeneratorError(
                "E014",
                "NGA returned unreadable JSON.",
                retryable=False,
            ) from None
        return _extract_content(payload)

    def _http_call(self, request):
        try:
            with self._urlopen(
                request,
                timeout=self.config.timeout_seconds,
                context=self._ssl_context,
            ) as response:
                return response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise _http_error(exc.code) from None
        except (TimeoutError, socket.timeout):
            raise NgaGeneratorError(
                "E012",
                "NGA request timed out.",
                retryable=True,
            ) from None
        except URLError as exc:
            retryable = isinstance(exc.reason, (TimeoutError, socket.timeout))
            raise NgaGeneratorError(
                "E012",
                "NGA request timed out." if retryable else "NGA connection or TLS negotiation failed.",
                retryable=retryable,
            ) from None
        except (ssl.SSLError, OSError):
            raise NgaGeneratorError(
                "E012",
                "NGA connection or TLS negotiation failed.",
                retryable=False,
            ) from None

    def _http_call_cancellable(self, request, cancel_event: Event) -> bytes | None:
        """Run the blocking HTTP call on a worker thread so cancellation can
        return promptly; the abandoned worker dies at its own timeout."""
        box: dict[str, Any] = {}

        def runner() -> None:
            try:
                box["raw"] = self._http_call(request)
            except BaseException as exc:  # noqa: BLE001 - forwarded below
                box["error"] = exc

        worker = Thread(target=runner, daemon=True, name="nga-http-call")
        worker.start()
        while worker.is_alive():
            if cancel_event.is_set():
                return None
            worker.join(timeout=0.25)
        if "error" in box:
            raise box["error"]
        return box.get("raw")

    def _send_cli(self, prompt: str, *, cancel_event: Event | None = None) -> str:
        """Invoke the already-authenticated local NGA CLI and parse its NDJSON stream.

        The CLI owns authentication (OAuth login, token storage, refresh), so no
        credential is required here. Text content is collected from NDJSON events
        of type ``text`` (``part.text``) and concatenated.
        """

        assert isinstance(self.config, NgaCliConfig)
        command = [
            self.config.cli_path,
            "run",
            "--model",
            self.config.model,
            "--format",
            "json",
            prompt,
        ]
        if sys.platform == "win32" and len(subprocess.list2cmdline(command)) > _WINDOWS_COMMAND_LINE_LIMIT:
            raise _prompt_exceeds_command_line_limit()
        try:
            if self._subprocess_run is not None:
                completed = self._subprocess_run(
                    command,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                    timeout=self.config.timeout_seconds,
                )
            else:
                completed = _run_cli_limited(
                    command,
                    timeout=self.config.timeout_seconds,
                    popen_fn=self._subprocess_popen,
                    cancel_event=cancel_event,
                )
        except GeneratorCanceled:
            raise
        except FileNotFoundError as exc:
            if getattr(exc, "winerror", None) == _WINERROR_FILENAME_TOO_LONG:
                raise _prompt_exceeds_command_line_limit() from exc
            raise NgaGeneratorError(
                "E010",
                "NGA CLI was not found; check the CLI path.",
                retryable=False,
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise NgaGeneratorError(
                "E012",
                "NGA CLI timed out.",
                retryable=True,
            ) from exc
        except _CliOutputLimitExceeded as exc:
            raise NgaGeneratorError(
                "E014",
                "NGA CLI output exceeded the allowed size.",
                retryable=False,
            ) from exc
        except OSError as exc:
            raise NgaGeneratorError(
                "E012",
                "NGA CLI could not be executed.",
                retryable=False,
            ) from exc

        if completed.returncode != 0:
            raise NgaGeneratorError(
                "E013",
                "NGA CLI exited with an error.",
                retryable=True,
            ) from None
        stdout = completed.stdout
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_NDJSON_BYTES:
            raise NgaGeneratorError(
                "E014",
                "NGA CLI output exceeded the allowed size.",
                retryable=False,
            )
        try:
            return _extract_ndjson_text(stdout)
        except NgaGeneratorError:
            raise
        except Exception as exc:
            raise NgaGeneratorError(
                "E014",
                "NGA CLI output could not be parsed.",
                retryable=False,
            ) from exc

    def _request(self, prompt: str, *, target: GeneratorTarget) -> Request:
        assert isinstance(self.config, NgaHttpConfig) and self._token is not None
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": _system_prompt(target)},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "stream": False,
        }
        if self.config.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        return Request(
            f"{self.config.base_url}{self.config.endpoint_path}",
            data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        if not isinstance(self.config, NgaHttpConfig) or not self.config.base_url.startswith("https://"):
            return None
        try:
            if not self.config.verify_tls:
                return ssl._create_unverified_context()
            if self.config.ca_bundle_path:
                path = Path(self.config.ca_bundle_path)
                if not path.is_file():
                    raise OSError("CA bundle does not exist")
                return ssl.create_default_context(cafile=str(path))
            return ssl.create_default_context()
        except (OSError, ssl.SSLError):
            raise NgaGeneratorError(
                "E010",
                "NGA TLS configuration is invalid.",
                retryable=False,
            ) from None


def _run_cli_limited(
    command: list[str],
    *,
    timeout: int,
    popen_fn: Callable[..., Any],
    cancel_event: Event | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a local CLI without buffering unbounded stdout or stderr in memory."""

    process = popen_fn(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    stdout_chunks: list[bytes] = []
    output_exceeded = Event()
    read_errors: list[BaseException] = []

    def drain(stream: Any, *, capture: bool) -> None:
        observed = 0
        retained = 0
        try:
            while chunk := stream.read(_CLI_STREAM_CHUNK_BYTES):
                observed += len(chunk)
                if capture:
                    if retained <= MAX_NDJSON_BYTES:
                        remaining = MAX_NDJSON_BYTES + 1 - retained
                        if remaining > 0:
                            retained += min(len(chunk), remaining)
                            stdout_chunks.append(chunk[:remaining])
                    # Only the captured NDJSON stream counts toward the output
                    # cap; chatty stderr logs must not fail a healthy run.
                    if observed > MAX_NDJSON_BYTES:
                        output_exceeded.set()
        except BaseException as exc:  # The caller maps all local CLI failures to sanitized codes.
            read_errors.append(exc)
        finally:
            try:
                stream.close()
            except OSError:
                pass

    readers = [
        Thread(target=drain, args=(process.stdout,), kwargs={"capture": True}, daemon=True),
        Thread(target=drain, args=(process.stderr,), kwargs={"capture": False}, daemon=True),
    ]
    for reader in readers:
        reader.start()

    deadline = time.monotonic() + timeout
    timed_out = False
    canceled = False
    while process.poll() is None:
        if cancel_event is not None and cancel_event.is_set():
            _stop_cli_process(process)
            canceled = True
            break
        if output_exceeded.is_set() or read_errors:
            _stop_cli_process(process)
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            _stop_cli_process(process)
            break
        time.sleep(min(0.05, remaining))

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _stop_cli_process(process)
        process.wait(timeout=5)
    for reader in readers:
        reader.join(timeout=5)

    # Re-check the cancel flag after the process has fully exited: a cancel
    # that lands in the last poll window would otherwise be missed and the
    # completed output returned as a normal success.
    if cancel_event is not None and cancel_event.is_set():
        raise GeneratorCanceled("NGA CLI process canceled")
    if canceled:
        raise GeneratorCanceled("NGA CLI process canceled")
    if timed_out:
        raise subprocess.TimeoutExpired(command, timeout)
    if output_exceeded.is_set():
        raise _CliOutputLimitExceeded()
    if read_errors:
        raise OSError("NGA CLI output stream could not be read") from read_errors[0]
    return subprocess.CompletedProcess(
        command,
        int(process.returncode or 0),
        stdout=b"".join(stdout_chunks).decode("utf-8", errors="replace"),
        stderr="",
    )


def _stop_cli_process(process: Any) -> None:
    """Terminate the CLI process and, where possible, its whole process tree.

    Killing only the direct child leaves grandchildren (node/rust-backed
    launchers) alive: they hold the inherited pipe ends open, so the drain
    threads block forever and every retry spawns another orphan.
    """
    pid = getattr(process, "pid", None)
    if os.name == "nt" and isinstance(pid, int):
        try:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
    elif isinstance(pid, int):
        try:
            os.killpg(pid, signal.SIGKILL)
            return
        except (OSError, ProcessLookupError):
            pass
    try:
        process.kill()
    except (OSError, ProcessLookupError):
        pass


def _prompt_exceeds_command_line_limit() -> NgaGeneratorError:
    return NgaGeneratorError(
        "E010",
        "NGA CLI prompt exceeds the Windows command-line length limit; "
        "use the HTTP transport or a smaller input.",
        retryable=False,
    )


def _http_error(status: int) -> NgaGeneratorError:
    if status in {401, 403}:
        return NgaGeneratorError(
            "E011",
            "NGA authentication was rejected.",
            retryable=False,
            http_status=status,
        )
    if status in RETRYABLE_HTTP_STATUSES:
        return NgaGeneratorError(
            "E013",
            "NGA is rate limited or temporarily unavailable.",
            retryable=True,
            http_status=status,
        )
    if status >= 500:
        return NgaGeneratorError(
            "E013",
            "NGA service returned an unrecoverable server error.",
            retryable=False,
            http_status=status,
        )
    return NgaGeneratorError(
        "E010",
        "NGA rejected the configured request.",
        retryable=False,
        http_status=status,
    )


def _extract_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise NgaGeneratorError("E014", "NGA response shape is invalid.", retryable=False)
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise NgaGeneratorError("E014", "NGA response does not contain choices.", retryable=False)
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise NgaGeneratorError("E014", "NGA response does not contain usable text.", retryable=False)
    return content.strip()


def _extract_ndjson_text(raw: str) -> str:
    """Parse NGA CLI NDJSON event stream, concatenating text from ``type=text`` events.

    Event types: step_start / text / tool_use / step_finish. Only ``text`` events
    carry model output, in ``part.text``.
    """

    if not raw.strip():
        raise NgaGeneratorError("E014", "NGA CLI returned no output.", retryable=False)
    chunks: list[str] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise NgaGeneratorError(
                "E014",
                f"NGA CLI emitted an unreadable event on line {line_number}.",
                retryable=False,
            ) from exc
        if not isinstance(event, dict):
            raise NgaGeneratorError("E014", "NGA CLI event is not a JSON object.", retryable=False)
        if event.get("type") != "text":
            continue
        part = event.get("part")
        text = part.get("text") if isinstance(part, dict) else None
        if isinstance(text, str):
            chunks.append(text)
    content = "".join(chunks).strip()
    if not content:
        raise NgaGeneratorError("E014", "NGA CLI output contains no usable text.", retryable=False)
    return content


def _system_prompt(target: GeneratorTarget) -> str:
    if target == "analysis":
        return "只返回用户要求的完整 JSON 对象，不要输出解释、代码围栏或额外文字。"
    target_name = "WordIR" if target == "word_ir" else "DeckIR"
    return (
        f"只返回一个符合用户所给 Schema 的完整 {target_name} JSON 对象；"
        "不要输出解释、代码围栏或 Schema 外字段。"
    )


def _environment_integer(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _environment_boolean(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")
