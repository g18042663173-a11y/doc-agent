from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from doc_agent.config import get_settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskMetadata(BaseModel):
    original_filename: str | None = None
    source_type: str | None = None
    target: str | None = None
    slides: int | None = None
    template_id: str | None = None
    color_scheme_id: str | None = None
    user_id: str | None = None
    profile_id: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class TaskRecord(BaseModel):
    task_id: str
    status: str
    progress: int
    current_step: str
    result: str | None = None
    error: str | None = None
    error_type: str | None = None
    friendly_error: str | None = None
    compliance_report: dict[str, Any] | None = None
    metadata: TaskMetadata = Field(default_factory=TaskMetadata)


class TaskHistoryManager:
    def __init__(self, tasks_dir: str | Path | None = None) -> None:
        self.tasks_dir = Path(tasks_dir) if tasks_dir else get_settings().data_dir / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def task_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{Path(task_id).name}.json"

    def create_task(
        self,
        task_id: str,
        status: str,
        progress: int,
        current_step: str,
        metadata: TaskMetadata | dict[str, Any] | None = None,
    ) -> TaskRecord:
        record = TaskRecord(
            task_id=task_id,
            status=status,
            progress=progress,
            current_step=current_step,
            metadata=self._coerce_metadata(metadata),
        )
        return self.save(record)

    def update_task(
        self,
        task_id: str,
        status: str,
        progress: int,
        current_step: str,
        result: str | None = None,
        error: str | None = None,
        error_type: str | None = None,
        friendly_error: str | None = None,
        compliance_report: dict[str, Any] | None = None,
    ) -> TaskRecord:
        record = self.get_task(task_id) or TaskRecord(task_id=task_id, status=status, progress=progress, current_step=current_step)
        record.status = status
        record.progress = progress
        record.current_step = current_step
        record.result = result
        record.error = error
        record.error_type = error_type
        record.friendly_error = friendly_error
        if compliance_report is not None:
            record.compliance_report = compliance_report
        record.metadata.updated_at = utc_now_iso()
        return self.save(record)

    def save(self, record: TaskRecord) -> TaskRecord:
        record.metadata.updated_at = utc_now_iso()
        self.task_path(record.task_id).write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return record

    def get_task(self, task_id: str) -> TaskRecord | None:
        path = self.task_path(task_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._normalize_record(data, task_id)

    def list_tasks(self, limit: int = 50) -> list[TaskRecord]:
        tasks: list[TaskRecord] = []
        for task_file in sorted(self.tasks_dir.glob("*.json")):
            try:
                task = self._normalize_record(json.loads(task_file.read_text(encoding="utf-8")), task_file.stem)
            except Exception:
                continue
            tasks.append(task)
        tasks.sort(key=lambda task: task.metadata.updated_at or task.metadata.created_at, reverse=True)
        return tasks[:limit]

    def delete_task(self, task_id: str, delete_files: bool = False) -> bool:
        record = self.get_task(task_id)
        path = self.task_path(task_id)
        existed = path.exists()
        if delete_files and record is not None:
            for candidate in [record.result]:
                if candidate:
                    file_path = Path(candidate)
                    if file_path.exists() and file_path.is_file():
                        file_path.unlink()
                    parent = file_path.parent
                    if parent.exists() and parent.is_dir():
                        shutil.rmtree(parent, ignore_errors=True)
        path.unlink(missing_ok=True)
        return existed

    @staticmethod
    def _coerce_metadata(metadata: TaskMetadata | dict[str, Any] | None) -> TaskMetadata:
        if metadata is None:
            return TaskMetadata()
        if isinstance(metadata, TaskMetadata):
            return metadata
        return TaskMetadata.model_validate(metadata)

    @classmethod
    def _normalize_record(cls, data: dict[str, Any], fallback_task_id: str) -> TaskRecord:
        metadata = data.get("metadata") or {}
        if "created_at" not in metadata:
            metadata["created_at"] = metadata.get("updated_at") or utc_now_iso()
        if "updated_at" not in metadata:
            metadata["updated_at"] = metadata.get("created_at") or utc_now_iso()
        normalized = {
            "task_id": data.get("task_id") or fallback_task_id,
            "status": data.get("status", "unknown"),
            "progress": data.get("progress", 0),
            "current_step": data.get("current_step", "Unknown"),
            "result": data.get("result"),
            "error": data.get("error"),
            "error_type": data.get("error_type"),
            "friendly_error": data.get("friendly_error"),
            "compliance_report": data.get("compliance_report"),
            "metadata": metadata,
        }
        return TaskRecord.model_validate(normalized)
