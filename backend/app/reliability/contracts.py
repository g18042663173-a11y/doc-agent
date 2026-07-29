from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FailureContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FailureItem(FailureContractModel):
    level: Literal["Error", "Warning", "Info"] = "Error"
    code: str = Field(min_length=3, max_length=16, pattern=r"^[A-Z][A-Z0-9-]+$")
    loc: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=500)
    suggestion: str = Field(min_length=1, max_length=500)


class FailureEnvelope(FailureContractModel):
    failure_envelope_version: Literal["1.0"] = "1.0"
    code: str = Field(min_length=3, max_length=16, pattern=r"^[A-Z][A-Z0-9-]+$")
    stage: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    retryable: bool
    message: str = Field(min_length=1, max_length=500)
    suggestion: str = Field(min_length=1, max_length=500)
    support_id: str = Field(pattern=r"^SUP-[0-9A-F]{12}$")
    loc: str | None = Field(default=None, min_length=1, max_length=200)
    items: list[FailureItem] = Field(default_factory=list, max_length=20)

    @field_validator("message", "suggestion", "loc")
    @classmethod
    def text_cannot_contain_line_breaks(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in "\r\n\x00"):
            raise ValueError("failure text must be a single sanitized line")
        return value


class JobState(FailureContractModel):
    job_state_version: Literal["1.0"] = "1.0"
    job_id: str = Field(pattern=r"^job-[0-9a-f]{32}$")
    target: Literal["word", "deck"]
    depth: Literal["概览", "标准", "详细"] | None = None
    generator_name: str = Field(default="stub", min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    generator_revision: int = Field(default=0, ge=0)
    status: Literal["pending", "running", "done", "failed", "canceled"]
    stage: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    progress_percent: int = Field(ge=0, le=100)
    error: FailureEnvelope | None = None
    artifact_path: str | None = None
    report: dict | None = None
    manifest: dict | None = None
    template_path: str | None = None
    asset_manifest_path: str | None = None
    assets: dict[str, str] = Field(default_factory=dict)
    template_summary: dict | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None

    @field_validator("artifact_path", "template_path", "asset_manifest_path")
    @classmethod
    def optional_paths_are_safe(cls, value: str | None) -> str | None:
        return _safe_relative_path(value) if value is not None else None

    @field_validator("assets")
    @classmethod
    def asset_paths_are_safe(cls, value: dict[str, str]) -> dict[str, str]:
        return {name: _safe_relative_path(path) for name, path in value.items()}


def _safe_relative_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("job state paths must stay inside the job directory")
    return Path(*path.parts).as_posix()


def write_reliability_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in {"failure_envelope": FailureEnvelope, "job_state": JobState}.items():
        path = output_dir / f"{name}.schema.json"
        schema = json.loads(json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True))
        path.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


def write_failure_schema(output_dir: Path) -> Path:
    return write_reliability_schemas(output_dir)[0]
