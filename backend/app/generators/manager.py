from __future__ import annotations

from dataclasses import dataclass
import json
from threading import Lock
import time
from typing import Callable, Literal

from app.generators.interface import IRTextGenerator
from app.generators.nga import NgaGenerator, NgaGeneratorError, NgaHttpConfig
from app.generators.stub import StubGenerator


GeneratorName = Literal["stub", "nga"]
NgaFactory = Callable[[NgaHttpConfig, str], IRTextGenerator]


@dataclass(frozen=True)
class GeneratorSnapshot:
    name: str
    revision: int
    generator: IRTextGenerator


@dataclass
class _Draft:
    name: GeneratorName
    revision: int
    config: NgaHttpConfig | None
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
    ) -> None:
        generator = initial_generator or StubGenerator()
        self._lock = Lock()
        self._counter = 0
        self._active = GeneratorSnapshot(
            name=generator.name,
            revision=self._counter,
            generator=generator,
        )
        initial_name: GeneratorName = "nga" if generator.name == "nga" else "stub"
        self._draft = _Draft(
            name=initial_name,
            revision=self._counter,
            config=getattr(generator, "config", None) if initial_name == "nga" else None,
            credential=None,
            tested=initial_name == "stub",
        )
        self._active_config = self._draft.config
        self._nga_factory = nga_factory or (lambda config, credential: NgaGenerator(config=config, token=credential))

    def configure(
        self,
        *,
        generator: GeneratorName,
        config: NgaHttpConfig | None = None,
        credential: str | None = None,
        clear_credential: bool = False,
    ) -> dict:
        if generator not in {"stub", "nga"}:
            raise NgaGeneratorError("E010", "Generator selection is invalid.", retryable=False)
        if generator == "nga" and config is None:
            raise NgaGeneratorError("E010", "NGA configuration is required.", retryable=False)
        if credential is not None:
            if not credential.strip() or len(credential) > 8192:
                raise NgaGeneratorError("E010", "NGA credential is invalid.", retryable=False)
            next_credential = credential
        else:
            next_credential = None

        with self._lock:
            if generator == "nga" and credential is None and not clear_credential and self._draft.name == "nga":
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
            return self._status_unlocked()

    def test_draft(self) -> dict[str, int | bool | str]:
        with self._lock:
            draft = _Draft(**self._draft.__dict__)
        if draft.name == "stub":
            return {"ok": True, "generator": "stub", "revision": draft.revision, "latency_ms": 0}
        if draft.config is None or not draft.credential:
            raise NgaGeneratorError("E010", "NGA configuration or credential is missing.", retryable=False)

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
            raise NgaGeneratorError("E010", "NGA configuration must pass a connection test before activation.", retryable=False)
        if draft.name == "stub":
            generator: IRTextGenerator = StubGenerator()
        else:
            if draft.config is None or not draft.credential:
                raise NgaGeneratorError("E010", "NGA configuration or credential is missing.", retryable=False)
            generator = self._nga_factory(draft.config, draft.credential)
        with self._lock:
            if self._draft.revision != draft.revision:
                raise NgaGeneratorError("E010", "Generator configuration changed before activation.", retryable=False)
            self._active = GeneratorSnapshot(
                name=draft.name,
                revision=draft.revision,
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
        active: dict = {
            "name": self._active.name,
            "revision": self._active.revision,
        }
        if self._active_config is not None:
            active["config"] = self._active_config.model_dump(mode="json")
        draft: dict = {
            "name": self._draft.name,
            "revision": self._draft.revision,
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
