from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.reliability.contracts import FailureEnvelope, JobState, write_reliability_schemas


ROOT = Path(__file__).resolve().parents[2]


def test_failure_envelope_is_strict_and_sanitized() -> None:
    payload = {
        "failure_envelope_version": "1.0",
        "code": "E001",
        "stage": "rendering",
        "retryable": False,
        "message": "任务执行失败。",
        "suggestion": "请下载失败报告。",
        "support_id": "SUP-0123456789AB",
    }
    assert FailureEnvelope.model_validate(payload).model_dump(exclude_none=True)["stage"] == "rendering"

    with pytest.raises(ValidationError):
        FailureEnvelope.model_validate({**payload, "message": "secret\ntraceback"})
    with pytest.raises(ValidationError):
        FailureEnvelope.model_validate({**payload, "raw_prompt": "must not be accepted"})


def test_failure_envelope_schema_matches_export(tmp_path: Path) -> None:
    for generated in write_reliability_schemas(tmp_path):
        expected = ROOT / "backend" / "schemas" / generated.name
        assert json.loads(generated.read_text(encoding="utf-8")) == json.loads(expected.read_text(encoding="utf-8"))


def test_job_state_rejects_absolute_and_parent_paths() -> None:
    base = {
        "job_id": "job-0123456789abcdef0123456789abcdef",
        "target": "deck",
        "status": "pending",
        "stage": "queued",
        "progress_percent": 0,
        "created_at": "2026-07-29T00:00:00Z",
        "updated_at": "2026-07-29T00:00:00Z",
    }
    assert JobState.model_validate({**base, "artifact_path": "deck.pptx"}).artifact_path == "deck.pptx"
    with pytest.raises(ValidationError):
        JobState.model_validate({**base, "artifact_path": "../outside.pptx"})
