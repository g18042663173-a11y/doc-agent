from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import ssl
import time
from typing import Any, Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


GeneratorTarget = Literal["word_ir", "deck_ir", "analysis"]
ResponseFormat = Literal["json_object", "none"]
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
RETRYABLE_HTTP_STATUSES = frozenset({429, 502, 503, 504})


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
        config: NgaHttpConfig | None = None,
        token: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
        urlopen_fn: Callable[..., Any] = urlopen,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if config is None:
            environment_base_url = base_url or os.environ.get("NGA_BASE_URL")
            environment_model = model or os.environ.get("NGA_MODEL")
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
        self._ssl_context = self._build_ssl_context()

    def __repr__(self) -> str:
        model = self.config.model if self.config is not None else "<unconfigured>"
        return f"NgaGenerator(model={model!r}, credential_configured={bool(self._token)})"

    def generate(self, prompt: str, *, target: GeneratorTarget) -> str:
        if self.config is None:
            raise NgaGeneratorError(
                "E010",
                "NGA configuration is incomplete.",
                retryable=False,
            )
        if not self._token:
            raise NgaGeneratorError(
                "E010",
                "NGA runtime credential is not configured.",
                retryable=False,
            )

        request = self._request(prompt, target=target)
        for attempt in range(self.config.max_retries + 1):
            try:
                return self._send(request)
            except NgaGeneratorError as exc:
                if not exc.retryable or attempt >= self.config.max_retries:
                    raise
                self._sleep(min(0.25 * (2**attempt), 2.0))
        raise AssertionError("NGA retry loop did not return or raise")

    def _request(self, prompt: str, *, target: GeneratorTarget) -> Request:
        assert self.config is not None and self._token is not None
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

    def _send(self, request: Request) -> str:
        assert self.config is not None
        try:
            with self._urlopen(
                request,
                timeout=self.config.timeout_seconds,
                context=self._ssl_context,
            ) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
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

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        if self.config is None or not self.config.base_url.startswith("https://"):
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
