from __future__ import annotations

from dataclasses import dataclass
import json
import os
from threading import Lock
import time
from typing import Callable, Literal

from app.generators.codex import CodexConfig, CodexGenerator
from app.generators.interface import IRTextGenerator
from app.generators.nga import NgaCliConfig, NgaGenerator, NgaGeneratorError, NgaHttpConfig
from app.generators.stub import StubGenerator


GeneratorName = Literal["stub", "nga", "codex"]
GeneratorMode = Literal["auto", "strict"]
NgaFactory = Callable[[NgaHttpConfig | NgaCliConfig, str], IRTextGenerator]
CodexFactory = Callable[[CodexConfig, str | None], IRTextGenerator]


@dataclass(frozen=True)
class GeneratorSnapshot:
    name: str
    revision: int
    generator: IRTextGenerator
    mode: GeneratorMode = "auto"


@dataclass
class _Draft:
    name: GeneratorName
    revision: int
    config: NgaHttpConfig | NgaCliConfig | CodexConfig | None
    credential: str | None
    tested: bool
    latency_ms: int | None = None


class GeneratorManager:
    """Own generator configuration without persisting credentials or mutating active jobs."""

    def __init__(
        self,
        *,
        initial_generator: IRTextGenerator | None = None,
        nga_factory: NgaFactory | None = None,
        codex_factory: CodexFactory | None = None,
        mode: GeneratorMode = "auto",
    ) -> None:
        if mode not in {"auto", "strict"}:
            raise NgaGeneratorError("E010", "Generator mode must be auto or strict.", retryable=False)
        generator = initial_generator or StubGenerator()
        self._lock = Lock()
        self._counter = 0
        self._active = GeneratorSnapshot(
            name=generator.name,
            revision=self._counter,
            mode=mode,
            generator=generator,
        )
        if generator.name == "nga":
            initial_name: GeneratorName = "nga"
            draft_config: NgaHttpConfig | NgaCliConfig | CodexConfig | None = getattr(generator, "config", None)
        elif generator.name == "codex":
            initial_name = "codex"
            draft_config = CodexConfig(
                base_url=generator.base_url,
                model=generator.model,
                api_mode=generator.api_mode,
                timeout_seconds=generator.timeout_seconds,
                reasoning_effort=generator.reasoning_effort,
            )
        else:
            initial_name = "stub"
            draft_config = None
        self._draft = _Draft(
            name=initial_name,
            revision=self._counter,
            config=draft_config,
            credential=None,
            tested=initial_name == "stub",
        )
        self._active_config = self._draft.config
        self._draft_mode: GeneratorMode = mode
        self._nga_factory = nga_factory or (lambda config, credential: NgaGenerator(config=config, token=credential))
        self._codex_factory = codex_factory or (
            lambda config, credential: CodexGenerator(
                api_key=credential,
                base_url=config.base_url,
                model=config.model,
                api_mode=config.api_mode,
                timeout_seconds=config.timeout_seconds,
                reasoning_effort=config.reasoning_effort,
            )
        )

    def configure(
        self,
        *,
        generator: GeneratorName,
        config: NgaHttpConfig | NgaCliConfig | CodexConfig | None = None,
        credential: str | None = None,
        clear_credential: bool = False,
        mode: GeneratorMode | None = None,
    ) -> dict:
        if generator not in {"stub", "nga", "codex"}:
            raise NgaGeneratorError("E010", "Generator selection is invalid.", retryable=False)
        if mode is not None and mode not in {"auto", "strict"}:
            raise NgaGeneratorError("E010", "Generator mode must be auto or strict.", retryable=False)
        if generator in {"nga", "codex"} and config is None:
            raise NgaGeneratorError("E010", f"{generator.upper()} configuration is required.", retryable=False)
        if credential is not None:
            if not credential.strip() or len(credential) > 8192:
                raise NgaGeneratorError("E010", "Generator credential is invalid.", retryable=False)
            next_credential = credential
        else:
            next_credential = None

        with self._lock:
            if generator in {"nga", "codex"} and credential is None and not clear_credential and self._draft.name == generator:
                next_credential = self._draft.credential
            if generator == "stub":
                config = None
                next_credential = None
            self._counter += 1
            self._draft = _Draft(
                name=generator,
                revision=self._counter,
                config=config,
                credential=next_credential,
                tested=generator == "stub",
            )
            if mode is not None:
                self._draft_mode = mode
            return self._status_unlocked()

    def test_draft(self) -> dict[str, int | bool | str]:
        with self._lock:
            draft = _Draft(**self._draft.__dict__)
        if draft.name == "stub":
            return {"ok": True, "generator": "stub", "revision": draft.revision, "latency_ms": 0}
        if draft.config is None:
            raise NgaGeneratorError("E010", "Generator configuration is missing.", retryable=False)
        if isinstance(draft.config, NgaHttpConfig) and not draft.credential:
            raise NgaGeneratorError("E010", "NGA credential is missing.", retryable=False)
        if draft.name == "codex":
            generator = self._codex_factory(draft.config, draft.credential)
        else:
            generator = self._nga_factory(draft.config, draft.credential)
        started = time.monotonic()
        raw = generator.generate(
            'NGA_CONNECTION_TEST: 只返回 {"ok":true}。',
            target="analysis",
        )
        try:
            response = json.loads(raw)
        except json.JSONDecodeError:
            raise NgaGeneratorError("E014", "NGA connection test returned invalid JSON.", retryable=False) from None
        if not isinstance(response, dict) or response.get("ok") is not True:
            raise NgaGeneratorError("E014", "NGA connection test returned an unexpected payload.", retryable=False)
        latency_ms = max(0, round((time.monotonic() - started) * 1000))
        with self._lock:
            if self._draft.revision != draft.revision:
                raise NgaGeneratorError("E010", "NGA configuration changed during its connection test.", retryable=False)
            self._draft.tested = True
            self._draft.latency_ms = latency_ms
        return {
            "ok": True,
            "generator": "nga",
            "revision": draft.revision,
            "latency_ms": latency_ms,
        }

    def activate(self) -> dict:
        with self._lock:
            draft = _Draft(**self._draft.__dict__)
        if not draft.tested:
            raise NgaGeneratorError("E010", "Generator configuration must pass a connection test before activation.", retryable=False)
        if draft.name == "stub":
            generator: IRTextGenerator = StubGenerator()
        elif draft.name == "codex":
            if draft.config is None:
                raise NgaGeneratorError("E010", "Generator configuration is missing.", retryable=False)
            # A missing credential falls back to the OPENAI_API_KEY environment
            # variable inside CodexGenerator; the connection test already
            # verified whichever credential source will be used.
            generator = self._codex_factory(draft.config, draft.credential)
        else:
            if draft.config is None:
                raise NgaGeneratorError("E010", "NGA configuration is missing.", retryable=False)
            if isinstance(draft.config, NgaHttpConfig) and not draft.credential:
                raise NgaGeneratorError("E010", "NGA credential is missing.", retryable=False)
            generator = self._nga_factory(draft.config, draft.credential)
        with self._lock:
            if self._draft.revision != draft.revision:
                raise NgaGeneratorError("E010", "Generator configuration changed before activation.", retryable=False)
            self._active = GeneratorSnapshot(
                name=draft.name,
                revision=draft.revision,
                mode=self._draft_mode,
                generator=generator,
            )
            self._active_config = draft.config
            return self._status_unlocked()

    def snapshot(self) -> GeneratorSnapshot:
        with self._lock:
            return self._active

    def status(self) -> dict:
        with self._lock:
            return self._status_unlocked()

    def _status_unlocked(self) -> dict:
        active_generator = self._active.generator
        active: dict = {
            "name": self._active.name,
            "revision": self._active.revision,
            "mode": self._active.mode,
            # Whether a credential is available for the active generator
            # (stored credential or OPENAI_API_KEY env). Never the value itself.
            "credential_configured": bool(
                getattr(active_generator, "_api_key", None) or os.environ.get("OPENAI_API_KEY")
            ),
        }
        if self._active_config is not None:
            active["config"] = self._active_config.model_dump(mode="json")
        draft: dict = {
            "name": self._draft.name,
            "revision": self._draft.revision,
            "mode": self._draft_mode,
            "credential_configured": bool(self._draft.credential),
            "tested": self._draft.tested,
            "latency_ms": self._draft.latency_ms,
        }
        if self._draft.config is not None:
            draft["config"] = self._draft.config.model_dump(mode="json")
        return {
            "settings_version": "1.0",
            "active": active,
            "draft": draft,
        }
