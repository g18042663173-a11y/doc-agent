from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
from pathlib import Path
from queue import Full, Queue
import re
import shutil
import sys
from threading import BoundedSemaphore, Event, Lock, Thread
import time
from typing import Any, Literal
from uuid import uuid4

from flask import Flask, jsonify, request, send_file
from pydantic import ValidationError

from app.assets.errors import AssetError
from app.assets.pipeline import AssetRegistry, load_asset_manifest, normalize_assets
from app.assets.extract import extract_office_image_files
from app.cli.parse import parse_file
from app.diagnostics import build_runtime_diagnostics
from app.generation.analysis import build_analysis_prompt, measure_document, validate_analysis_text
from app.generation.depth import GenerationOptions, generate_deck
from app.generators.interface import IRTextGenerator
from app.generators.manager import GeneratorManager
from app.generators.nga import (
    NgaCliConfig,
    NgaGeneratorError,
    NgaHttpConfig,
)
from app.generators.stub import StubGenerator
from app.ir.document_ir import DocumentIR
from app.ir.errors import ValidationResult
from app.ir.repair import repair_generated_text, repair_ir_text
from app.lint.docx_lint import check_docx, write_docx_reports
from app.lint.pptx_lint import check_pptx, write_reports
from app.prompting.builder import Depth, build_prompt
from app.parsers.errors import ParseFailure
from app.reliability.contracts import FailureEnvelope, JobState
from app.rendering.docx_renderer import render_word_ir
from app.rendering.pptx_renderer import render_deck_ir
from app.rendering.theme import THEME_REGISTRY
from app.template.package import TemplateInputError, validate_pptx_package, validate_template_package
from app.template.planner import build_template_plan
from app.template.profile import extract_template_profile
from app.template.renderer import render_deck_ir_with_template
from app.version import APP_VERSION
from app.visual.planner import audit_visual_selection, build_visual_plan


ALLOWED_INPUT_SUFFIXES = {".md", ".docx", ".xlsx", ".pptx"}
ALLOWED_DOWNLOAD_ASSETS = {
    "output",
    "lint",
    "profile",
    "plan",
    "structure",
    "replacement-audit",
    "package-report",
    "failure-report",
    "asset-manifest",
    "asset-usage-audit",
    "visual-plan",
    "visual-selection-audit",
    "deck-ir",
}
MAX_INPUT_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_TEMPLATE_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_ASSET_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_ASSET_TOTAL_BYTES = 100 * 1024 * 1024
MAX_ASSET_UPLOADS = 20
MIN_FREE_DISK_BYTES = 512 * 1024 * 1024
REQUEST_WORKING_SPACE_MULTIPLIER = 3
UPLOAD_CHUNK_BYTES = 1024 * 1024
TargetKind = Literal["word", "deck"]
JobStatus = Literal["pending", "running", "done", "failed", "canceled"]
TERMINAL_JOB_STATUSES = {"done", "failed", "canceled"}
JOB_DIRECTORY_RE = re.compile(r"^job-[0-9a-f]{32}$")
IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
DEFAULT_JOB_TIMEOUT_SECONDS = 900.0
DEFAULT_QUEUE_CAPACITY = 4
DEFAULT_RETENTION_HOURS = 24
DEFAULT_RATE_LIMIT_PER_MINUTE = 30
API_VERSION = "1.0"


@dataclass
class ApiJob:
    job_id: str
    target: TargetKind
    depth: Depth | None
    work_dir: Path
    theme: str = "hw_v1"
    generator_name: str = "stub"
    generator_revision: int = 0
    generator_mode: str = "auto"
    generator_fallback: bool = False
    status: JobStatus = "pending"
    stage: str = "queued"
    progress_percent: int = 0
    error: dict[str, Any] | None = None
    artifact_path: Path | None = None
    report: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    template_path: Path | None = None
    asset_manifest_path: Path | None = None
    assets: dict[str, Path] = field(default_factory=dict)
    template_summary: dict[str, Any] | None = None
    idempotency_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": self.job_id,
            "type": self.target,
            "depth": self.depth,
            "theme": self.theme,
            "generator": {
                "name": self.generator_name,
                "revision": self.generator_revision,
                "mode": self.generator_mode,
                "fallback": self.generator_fallback,
            },
            "status": self.status,
            "progress": {"stage": self.stage, "percent": self.progress_percent},
        }
        if self.status == "done" and self.artifact_path is not None:
            payload["artifact"] = {
                "name": self.artifact_path.name,
                "download_url": f"/api/download/{self.job_id}",
            }
            payload["report"] = self.report
            if self.manifest is not None:
                payload["generation_manifest"] = self.manifest
            if self.template_summary is not None:
                payload["template"] = self.template_summary
        if self.assets:
            payload["assets"] = {
                name: {"name": path.name, "download_url": f"/api/download/{self.job_id}/{name}"}
                for name, path in sorted(self.assets.items())
            }
        if self.status in {"failed", "canceled"}:
            payload["error"] = self.error
        return payload


@dataclass
class JobStore:
    root: Path
    retention: timedelta = field(default_factory=lambda: timedelta(hours=DEFAULT_RETENTION_HOURS))
    _jobs: dict[str, ApiJob] = field(default_factory=dict)
    _idempotency: dict[str, str] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    recovery_warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        self._load()

    def create(
        self,
        *,
        target: TargetKind,
        depth: Depth | None,
        theme: str = "hw_v1",
        work_dir: Path,
        generator_name: str = "stub",
        generator_revision: int = 0,
        generator_mode: str = "auto",
        generator_fallback: bool = False,
        template_path: Path | None = None,
        asset_manifest_path: Path | None = None,
        idempotency_key: str | None = None,
    ) -> ApiJob:
        job = ApiJob(
            job_id=work_dir.name,
            target=target,
            depth=depth,
            theme=theme,
            work_dir=work_dir,
            generator_name=generator_name,
            generator_revision=generator_revision,
            generator_mode=generator_mode,
            generator_fallback=generator_fallback,
            template_path=template_path,
            asset_manifest_path=asset_manifest_path,
            idempotency_key=idempotency_key,
        )
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency:
                raise ValueError("idempotency key already exists")
            self._jobs[job.job_id] = job
            if idempotency_key:
                self._idempotency[idempotency_key] = job.job_id
            self._persist_unlocked(job)
        return job

    def get(self, job_id: str) -> ApiJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_by_idempotency_key(self, key: str) -> ApiJob | None:
        with self._lock:
            job_id = self._idempotency.get(key)
            return self._jobs.get(job_id) if job_id is not None else None

    def update(self, job_id: str, **changes: Any) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status in TERMINAL_JOB_STATUSES:
                return False
            for field_name, value in changes.items():
                setattr(job, field_name, value)
            job.updated_at = datetime.now(timezone.utc)
            if job.status in TERMINAL_JOB_STATUSES and job.expires_at is None:
                job.expires_at = job.updated_at + self.retention
            self._persist_unlocked(job)
            return True

    def payload(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return None if job is None else job.payload()

    def stats(self) -> dict[str, int]:
        with self._lock:
            counts = {status: 0 for status in ["pending", "running", "done", "failed", "canceled"]}
            for job in self._jobs.values():
                counts[job.status] += 1
            counts["total"] = len(self._jobs)
            return counts

    def list_payloads(self) -> list[dict[str, Any]]:
        with self._lock:
            ordered = sorted(
                self._jobs.values(),
                key=lambda job: (job.created_at, job.job_id),
                reverse=True,
            )
            return [job.payload() for job in ordered]

    def interrupted(self) -> list[ApiJob]:
        with self._lock:
            return [job for job in self._jobs.values() if job.status in {"pending", "running"}]

    def cleanup_expired(self, *, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        expired: list[ApiJob] = []
        with self._lock:
            for job in self._jobs.values():
                if job.expires_at is not None and job.expires_at <= current:
                    expired.append(job)
            for job in expired:
                self._jobs.pop(job.job_id, None)
                if job.idempotency_key:
                    self._idempotency.pop(job.idempotency_key, None)
        for job in expired:
            _remove_job_directory(self.root, job.work_dir)
        return len(expired)

    def _load(self) -> None:
        for work_dir in sorted(self.root.iterdir()):
            if not work_dir.is_dir() or not JOB_DIRECTORY_RE.fullmatch(work_dir.name):
                continue
            state_path = work_dir / "job_state.json"
            if not state_path.is_file():
                continue
            try:
                state = JobState.model_validate_json(state_path.read_text(encoding="utf-8"))
                if state.job_id != work_dir.name:
                    raise ValueError("job id does not match directory")
                job = _api_job_from_state(work_dir, state)
            except Exception:
                self.recovery_warnings.append(f"ignored invalid job state: {work_dir.name}")
                continue
            self._jobs[job.job_id] = job
            if job.idempotency_key:
                self._idempotency[job.idempotency_key] = job.job_id

    def _persist_unlocked(self, job: ApiJob) -> None:
        state = _job_state(job)
        path = job.work_dir / "job_state.json"
        temporary = job.work_dir / "job_state.json.tmp"
        temporary.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)


@dataclass(frozen=True)
class QueuedJob:
    job_id: str
    input_path: Path
    generator: IRTextGenerator
    generator_revision: int


class JobRunner:
    def __init__(
        self,
        *,
        jobs: JobStore,
        timeout_seconds: float,
        queue_capacity: int,
    ) -> None:
        self.jobs = jobs
        self.timeout_seconds = timeout_seconds
        self.queue_capacity = queue_capacity
        self._queue: Queue[QueuedJob] = Queue(maxsize=queue_capacity + 1)
        self._slots = BoundedSemaphore(queue_capacity + 1)
        self._worker = Thread(target=self._loop, daemon=True, name="web-api-worker")
        self._worker.start()
        self._supervisor = Thread(target=self._supervise, daemon=True, name="web-api-supervisor")
        self._supervisor.start()

    def reserve(self) -> bool:
        return self._slots.acquire(blocking=False)

    def release_reservation(self) -> None:
        self._slots.release()

    def submit_reserved(self, item: QueuedJob) -> None:
        try:
            self._queue.put_nowait(item)
        except Full:
            self._slots.release()
            raise

    def stats(self) -> dict[str, Any]:
        return {
            "worker_alive": self._worker.is_alive(),
            "queue_capacity": self.queue_capacity,
            "queued": self._queue.qsize(),
            "timeout_seconds": self.timeout_seconds,
        }

    def _supervise(self) -> None:
        """Restart the worker thread if it ever dies so the queue never stalls."""
        while True:
            time.sleep(5)
            if not self._worker.is_alive():
                print(
                    "web-api: worker thread died; restarting it",
                    file=sys.stderr,
                    flush=True,
                )
                self._worker = Thread(target=self._loop, daemon=True, name="web-api-worker")
                self._worker.start()

    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                job = self.jobs.get(item.job_id)
                if job is None or job.status in TERMINAL_JOB_STATUSES:
                    continue
                finished = Event()

                def execute() -> None:
                    try:
                        _run_job(
                            job_id=item.job_id,
                            input_path=item.input_path,
                            generator=item.generator,
                            jobs=self.jobs,
                        )
                    finally:
                        try:
                            current = self.jobs.get(item.job_id)
                            if current is not None and current.status in {"failed", "canceled"}:
                                _cleanup_sensitive_job_files(current)
                        finally:
                            finished.set()

                task = Thread(target=execute, daemon=True, name=f"job-task-{item.job_id}")
                task.start()
                deadline = time.monotonic() + self.timeout_seconds
                while not finished.wait(timeout=0.1):
                    current = self.jobs.get(item.job_id)
                    if current is None or current.status == "canceled":
                        break
                    if time.monotonic() >= deadline:
                        _fail_job(
                            current,
                            self.jobs,
                            code="E002",
                            stage="timed_out",
                            retryable=True,
                            message="任务超过允许的总执行时间。",
                            suggestion="请减少输入复杂度后重试；若持续失败，请提供支持编号。",
                        )
                        break
            except Exception as exc:
                # A persistence/disk failure while marking a job failed must not
                # kill the only worker: fall back to marking the job failed and
                # keep consuming the queue. The supervisor restarts the worker
                # as a last resort if this ever escapes.
                print(
                    f"web-api: worker loop error for job {item.job_id}: {exc!r}",
                    file=sys.stderr,
                    flush=True,
                )
                try:
                    current = self.jobs.get(item.job_id)
                    if current is not None and current.status not in TERMINAL_JOB_STATUSES:
                        _fail_job(
                            current,
                            self.jobs,
                            code="E002",
                            stage="timed_out",
                            retryable=True,
                            message="任务超过允许的总执行时间，且失败记录写入失败。",
                            suggestion="请检查磁盘空间后重试。",
                        )
                except Exception as nested:
                    print(
                        f"web-api: fallback failure marking job {item.job_id}: {nested!r}",
                        file=sys.stderr,
                        flush=True,
                    )
            finally:
                self._queue.task_done()
                self._slots.release()


@dataclass
class RateLimiter:
    max_requests: int
    window_seconds: float = 60.0
    _requests: dict[str, list[float]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            recent = [timestamp for timestamp in self._requests.get(key, []) if timestamp >= cutoff]
            if len(recent) >= self.max_requests:
                self._requests[key] = recent
                return False
            recent.append(now)
            self._requests[key] = recent
            return True


def _require_desktop_session(session_token: str | None):
    if session_token is None or not request.path.startswith("/api/"):
        return None
    supplied = request.headers.get("X-Workbench-Session", "")
    if supplied and hmac.compare_digest(supplied, session_token):
        return None
    return _error_response(
        "E001",
        "桌面会话凭据无效。",
        status=401,
        stage="session_authentication",
        loc="X-Workbench-Session",
        suggestion="请重新启动文档生成工作台。",
        retryable=False,
    )


def _health_response(root: Path, runner: JobRunner, manager: GeneratorManager, jobs: JobStore):
    try:
        free_bytes = shutil.disk_usage(root).free
    except OSError:
        free_bytes = 0
    runner_state = runner.stats()
    generator_snapshot = manager.snapshot()
    ready = bool(runner_state["worker_alive"]) and free_bytes >= MIN_FREE_DISK_BYTES
    payload = {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "version": APP_VERSION,
        "generator": generator_snapshot.name,
        "generator_revision": generator_snapshot.revision,
        "jobs": jobs.stats(),
        "runner": runner_state,
        "storage": {
            "free_bytes": free_bytes,
            "minimum_free_bytes": MIN_FREE_DISK_BYTES,
        },
        "recovery_warning_count": len(jobs.recovery_warnings),
    }
    return jsonify(payload), 200 if ready else 503


def _diagnostics_response(root: Path, runner: JobRunner, manager: GeneratorManager, jobs: JobStore):
    try:
        free_bytes = shutil.disk_usage(root).free
    except OSError:
        free_bytes = 0
    generator_snapshot = manager.snapshot()
    return jsonify(
        build_runtime_diagnostics(
            app_version=APP_VERSION,
            api_version=API_VERSION,
            deck_ir_version="2.0",
            generator=generator_snapshot.name,
            generator_revision=generator_snapshot.revision,
            jobs=jobs.stats(),
            runner=runner.stats(),
            storage_free_bytes=free_bytes,
            storage_minimum_free_bytes=MIN_FREE_DISK_BYTES,
        )
    )


def _update_generator_settings(app: Flask, manager: GeneratorManager):
    try:
        _enforce_rate_limit(app)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ApiRequestError(
                "E010",
                "生成器配置必须是 JSON 对象。",
                status=400,
                stage="configuring_generator",
                retryable=False,
            )
        allowed = {"generator", "config", "credential", "clear_credential", "mode"}
        if set(payload) - allowed:
            raise ApiRequestError(
                "E010",
                "生成器配置包含未知字段。",
                status=400,
                stage="configuring_generator",
                retryable=False,
            )
        generator_name = payload.get("generator")
        if generator_name not in {"stub", "nga"}:
            raise ApiRequestError(
                "E010",
                "generator 只支持 stub 或 nga。",
                status=400,
                stage="configuring_generator",
                loc="generator",
                retryable=False,
            )
        mode = payload.get("mode")
        if mode is not None and mode not in {"auto", "strict"}:
            raise ApiRequestError(
                "E010",
                "mode 只支持 auto 或 strict。",
                status=400,
                stage="configuring_generator",
                loc="mode",
                retryable=False,
            )
        config_payload = payload.get("config")
        if generator_name == "nga":
            if not isinstance(config_payload, dict):
                raise ApiRequestError(
                    "E010",
                    "NGA 配置必须是 JSON 对象。",
                    status=400,
                    stage="configuring_generator",
                    loc="config",
                    retryable=False,
                )
            config = _nga_config_from_payload(config_payload)
        else:
            config = None
        credential = payload.get("credential")
        if credential is not None and not isinstance(credential, str):
            raise ApiRequestError(
                "E010",
                "NGA credential 必须是字符串。",
                status=400,
                stage="configuring_generator",
                loc="credential",
                retryable=False,
            )
        clear_credential = payload.get("clear_credential", False)
        if not isinstance(clear_credential, bool):
            raise ApiRequestError(
                "E010",
                "clear_credential 必须是布尔值。",
                status=400,
                stage="configuring_generator",
                loc="clear_credential",
                retryable=False,
            )
        return jsonify(
            manager.configure(
                generator=generator_name,
                config=config,
                credential=credential,
                clear_credential=clear_credential,
                mode=mode,
            )
        )
    except ValidationError:
        return _error_response(
            "E010",
            "NGA 配置字段无效。",
            status=400,
            stage="configuring_generator",
            suggestion="请检查地址、接口路径、模型、超时和 TLS 设置。",
            retryable=False,
        )
    except NgaGeneratorError as exc:
        return _generator_error_response(exc, stage="configuring_generator")
    except ApiRequestError as exc:
        return _api_request_error_response(exc)


def _nga_config_from_payload(config_payload: dict[str, Any]) -> NgaHttpConfig | NgaCliConfig:
    transport = config_payload.get("transport", "http")
    if transport == "cli":
        cli_fields = {
            "config_version": config_payload.get("config_version", "1.0"),
            "transport": "cli",
            "model": config_payload.get("model"),
            "cli_path": config_payload.get("cli_path", "nga"),
            "timeout_seconds": config_payload.get("timeout_seconds", 300),
            "max_retries": config_payload.get("max_retries", 2),
        }
        return NgaCliConfig.model_validate(cli_fields)
    http_fields = {
        "config_version": config_payload.get("config_version", "1.0"),
        "base_url": config_payload.get("base_url"),
        "endpoint_path": config_payload.get("endpoint_path", "/v1/chat/completions"),
        "model": config_payload.get("model"),
        "timeout_seconds": config_payload.get("timeout_seconds", 120),
        "max_retries": config_payload.get("max_retries", 2),
        "verify_tls": config_payload.get("verify_tls", True),
        "ca_bundle_path": config_payload.get("ca_bundle_path"),
        "response_format": config_payload.get("response_format", "json_object"),
        "allow_insecure_http": config_payload.get("allow_insecure_http", False),
    }
    return NgaHttpConfig.model_validate(http_fields)


def _test_generator_settings(app: Flask, manager: GeneratorManager):
    try:
        _enforce_rate_limit(app)
        return jsonify({"connection": manager.test_draft(), **manager.status()})
    except NgaGeneratorError as exc:
        return _generator_error_response(exc, stage="testing_generator")


def _activate_generator_settings(app: Flask, manager: GeneratorManager):
    try:
        _enforce_rate_limit(app)
        return jsonify(manager.activate())
    except NgaGeneratorError as exc:
        return _generator_error_response(exc, stage="activating_generator", conflict=True)


def _analyze_request(app: Flask, root: Path, manager: GeneratorManager):
    analysis_dir: Path | None = None
    try:
        _enforce_rate_limit(app)
        _ensure_disk_capacity(root)
        analysis_dir = _new_workspace(root, prefix="analysis")
        input_path = _save_upload(analysis_dir)
        document = parse_file(input_path)
        metrics = measure_document(document)
        generator_snapshot = manager.snapshot()
        raw = generator_snapshot.generator.generate(build_analysis_prompt(document, metrics), target="analysis")
        result = repair_generated_text(
            raw,
            target="analysis",
            generator=generator_snapshot.generator,
            validator=lambda current: validate_analysis_text(
                current,
                expected_metrics=metrics,
                expected_filename=document.source.filename,
            ),
        )
        if not result.ok or result.value is None:
            return _validation_error(result)
        return jsonify(result.value.model_dump(mode="json"))
    except Exception as exc:
        return _analysis_error_response(exc)
    finally:
        if analysis_dir is not None:
            shutil.rmtree(analysis_dir, ignore_errors=True)


def _analysis_error_response(exc: Exception):
    if isinstance(exc, ApiRequestError):
        return _api_request_error_response(exc)
    if isinstance(exc, ParseFailure):
        return _error_response(
            exc.code,
            "源文件无法解析。",
            status=422,
            stage="parsing",
            loc=exc.loc,
            suggestion="请确认文件未损坏、扩展名与实际格式一致后重试。",
            retryable=False,
        )
    if isinstance(exc, NgaGeneratorError):
        return _generator_error_response(exc, stage="analyzing")
    if isinstance(exc, TimeoutError):
        return _error_response(
            "E002",
            "内容分析服务响应超时。",
            status=504,
            stage="analyzing",
            suggestion="请稍后重试；若持续失败，请提供支持编号。",
            retryable=True,
        )
    return _error_response(
        "E001",
        "分析任务执行失败。",
        status=500,
        stage="analyzing",
        suggestion="请稍后重试；若持续失败，请提供支持编号。",
        retryable=True,
    )


def _generate_request(
    app: Flask,
    root: Path,
    jobs: JobStore,
    runner: JobRunner,
    manager: GeneratorManager,
):
    job_dir: Path | None = None
    reserved = False
    response_status = 202
    try:
        idempotency_key = _idempotency_key()
        jobs.cleanup_expired()
        if idempotency_key:
            existing = jobs.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return jsonify(existing.payload()), 200 if existing.status in TERMINAL_JOB_STATUSES else 202
        _enforce_rate_limit(app)
        _ensure_disk_capacity(root)
        target = _target_from_form()
        _preflight_generator_environment(manager, target=target)
        depth = _depth_from_form(target)
        theme = _theme_from_form(target)
        if not runner.reserve():
            raise ApiRequestError(
                "E008",
                "当前任务队列已满。",
                status=429,
                stage="queued",
                suggestion="请等待已有任务完成后重试。",
                retryable=True,
            )
        reserved = True
        job_dir = _new_workspace(root, prefix="job")
        input_path = _save_upload(job_dir)
        template_path = _save_template_upload(job_dir, target)
        asset_manifest_path = _save_asset_uploads(job_dir, target)
    except ApiRequestError as exc:
        if reserved:
            runner.release_reservation()
        if job_dir is not None:
            shutil.rmtree(job_dir, ignore_errors=True)
        return _api_request_error_response(exc)

    try:
        generator_snapshot = manager.snapshot()
        job = jobs.create(
            target=target,
            depth=depth,
            theme=theme,
            work_dir=job_dir,
            generator_name=generator_snapshot.name,
            generator_revision=generator_snapshot.revision,
            generator_mode=generator_snapshot.mode,
            template_path=template_path,
            asset_manifest_path=asset_manifest_path,
            idempotency_key=idempotency_key,
        )
        runner.submit_reserved(
            QueuedJob(
                job_id=job.job_id,
                input_path=input_path,
                generator=generator_snapshot.generator,
                generator_revision=generator_snapshot.revision,
            )
        )
        reserved = False
    except ValueError:
        if reserved:
            runner.release_reservation()
        shutil.rmtree(job_dir, ignore_errors=True)
        existing = jobs.get_by_idempotency_key(idempotency_key or "")
        if existing is None:
            return _error_response(
                "E001",
                "任务创建失败。",
                status=500,
                stage="queued",
                suggestion="请稍后重试；若持续失败，请提供支持编号。",
                retryable=True,
            )
        job = existing
        response_status = 200 if existing.status in TERMINAL_JOB_STATUSES else 202
    return jsonify(job.payload()), response_status


def _job_status_response(jobs: JobStore, job_id: str):
    jobs.cleanup_expired()
    payload = jobs.payload(job_id)
    if payload is None:
        return _error_response("E001", "任务不存在。", status=404)
    return jsonify(payload)


def _artifact_download_response(jobs: JobStore, job_id: str):
    jobs.cleanup_expired()
    job = jobs.get(job_id)
    if job is None:
        return _error_response("E001", "任务不存在。", status=404)
    if job.status != "done" or job.artifact_path is None:
        return _error_response("E001", "任务尚未完成，暂无可下载产物。", status=409)
    if not job.artifact_path.is_file():
        return _error_response("E001", "任务产物不存在。", status=404)
    return send_file(job.artifact_path, as_attachment=True, download_name=job.artifact_path.name)


def _audit_download_response(jobs: JobStore, job_id: str, asset: str):
    if asset not in ALLOWED_DOWNLOAD_ASSETS:
        return _error_response(
            "E001",
            "asset 不在允许下载的审计文件白名单中。",
            status=400,
        )
    jobs.cleanup_expired()
    job = jobs.get(job_id)
    if job is None:
        return _error_response("E001", "任务不存在。", status=404)
    failure_report_available = job.status in {"failed", "canceled"} and asset == "failure-report"
    if job.status != "done" and not failure_report_available:
        return _error_response("E001", "任务尚未完成，暂无可下载审计文件。", status=409)
    path = job.artifact_path if asset == "output" else job.assets.get(asset)
    if path is None or not path.is_file():
        return _error_response("E001", "审计文件不存在。", status=404)
    return send_file(path, as_attachment=True, download_name=path.name)


def _cancel_job_response(jobs: JobStore, job_id: str):
    job = jobs.get(job_id)
    if job is None:
        return _error_response("E001", "任务不存在。", status=404, stage="canceling")
    if job.status in TERMINAL_JOB_STATUSES:
        return _error_response(
            "E001",
            "任务已结束，无法取消。",
            status=409,
            stage="canceling",
            suggestion="请查看现有任务结果，或创建新的任务。",
            retryable=False,
        )
    _fail_job(
        job,
        jobs,
        code="E009",
        stage="canceled",
        retryable=False,
        message="任务已取消。",
        suggestion="可修改输入后创建新的任务。",
        terminal_status="canceled",
    )
    return jsonify(jobs.payload(job_id)), 200


def _register_session_guard(app: Flask, session_token: str | None) -> None:
    @app.before_request
    def require_desktop_session():
        return _require_desktop_session(session_token)


def _register_service_routes(
    app: Flask,
    root: Path,
    jobs: JobStore,
    runner: JobRunner,
    manager: GeneratorManager,
) -> None:
    @app.get("/api/version")
    def version():
        return jsonify(
            {
                "service": "huawei-document-generator",
                "app_version": APP_VERSION,
                "api_version": API_VERSION,
                "deck_ir_version": "2.0",
                "failure_envelope_version": "1.0",
                "job_state_version": "1.0",
            }
        )

    @app.get("/api/health")
    def health():
        return _health_response(root, runner, manager, jobs)

    @app.get("/api/diagnostics")
    def diagnostics():
        return _diagnostics_response(root, runner, manager, jobs)

    @app.get("/api/jobs")
    def list_jobs():
        jobs.cleanup_expired()
        return jsonify({"jobs": jobs.list_payloads()})


def _register_generator_routes(app: Flask, manager: GeneratorManager) -> None:
    @app.get("/api/settings/generator")
    def generator_settings():
        return jsonify(manager.status())

    @app.put("/api/settings/generator")
    def update_generator_settings():
        return _update_generator_settings(app, manager)

    @app.post("/api/settings/generator/test")
    def test_generator_settings():
        return _test_generator_settings(app, manager)

    @app.post("/api/settings/generator/activate")
    def activate_generator_settings():
        return _activate_generator_settings(app, manager)


def _register_generation_routes(
    app: Flask,
    root: Path,
    jobs: JobStore,
    runner: JobRunner,
    manager: GeneratorManager,
) -> None:
    @app.post("/api/analyze")
    def analyze():
        return _analyze_request(app, root, manager)

    @app.post("/api/generate")
    def generate():
        return _generate_request(app, root, jobs, runner, manager)


def _register_job_routes(app: Flask, jobs: JobStore) -> None:
    @app.get("/api/status/<job_id>")
    def status(job_id: str):
        return _job_status_response(jobs, job_id)

    @app.get("/api/download/<job_id>")
    def download(job_id: str):
        return _artifact_download_response(jobs, job_id)

    @app.get("/api/download/<job_id>/<asset>")
    def download_asset(job_id: str, asset: str):
        return _audit_download_response(jobs, job_id, asset)

    @app.post("/api/jobs/<job_id>/cancel")
    def cancel(job_id: str):
        return _cancel_job_response(jobs, job_id)


def create_api_app(
    *,
    work_dir: Path | None = None,
    generator: IRTextGenerator | None = None,
    generator_manager: GeneratorManager | None = None,
    session_token: str | None = None,
    job_timeout_seconds: float = DEFAULT_JOB_TIMEOUT_SECONDS,
    queue_capacity: int = DEFAULT_QUEUE_CAPACITY,
    retention_hours: int = DEFAULT_RETENTION_HOURS,
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE,
) -> Flask:
    """Create the JSON API shared by the browser and protected desktop clients.

    The deterministic stub remains the default. NGA is enabled only after an
    explicit configure, connection-test, and activate sequence.
    """

    app = Flask(__name__)
    root = (work_dir or Path("output") / "web_api").resolve()
    root.mkdir(parents=True, exist_ok=True)
    if generator is not None and generator_manager is not None:
        raise ValueError("generator and generator_manager are mutually exclusive")
    manager = generator_manager or GeneratorManager(initial_generator=generator or StubGenerator())
    jobs = JobStore(root=root, retention=timedelta(hours=retention_hours))
    jobs.cleanup_expired()
    _recover_interrupted_jobs(jobs)
    runner = JobRunner(
        jobs=jobs,
        timeout_seconds=job_timeout_seconds,
        queue_capacity=queue_capacity,
    )
    app.config["API_WORK_DIR"] = root
    app.config["API_GENERATOR_MANAGER"] = manager
    app.config["API_JOBS"] = jobs
    app.config["API_JOB_RUNNER"] = runner
    app.config["API_RATE_LIMITER"] = RateLimiter(max_requests=rate_limit_per_minute)
    app.config["MAX_CONTENT_LENGTH"] = 260 * 1024 * 1024

    @app.errorhandler(413)
    def _request_too_large(_exc):
        # werkzeug raises this before any view runs; Flask's default handler
        # returns an HTML page that breaks the desktop client's JSON parsing.
        return _error_response(
            "E004",
            "请求体超过允许的大小限制。",
            status=413,
            stage="request_validation",
            suggestion="请拆分输入或压缩文件后重试。",
            retryable=False,
        )

    _register_session_guard(app, session_token)
    _register_service_routes(app, root, jobs, runner, manager)
    _register_generator_routes(app, manager)
    _register_generation_routes(app, root, jobs, runner, manager)
    _register_job_routes(app, jobs)
    return app


def _new_workspace(root: Path, *, prefix: str) -> Path:
    path = root / f"{prefix}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _idempotency_key() -> str | None:
    value = request.headers.get("Idempotency-Key", "").strip()
    if not value:
        return None
    if not IDEMPOTENCY_KEY_RE.fullmatch(value):
        raise ApiRequestError(
            "E001",
            "Idempotency-Key 格式不合法。",
            status=400,
            loc="Idempotency-Key",
            suggestion="请使用 8-128 位字母、数字、点、下划线、冒号或连字符。",
        )
    return value


def _enforce_rate_limit(app: Flask) -> None:
    limiter: RateLimiter = app.config["API_RATE_LIMITER"]
    client = request.remote_addr or "local"
    if not limiter.allow(client):
        raise ApiRequestError(
            "E008",
            "请求过于频繁。",
            status=429,
            stage="rate_limited",
            suggestion="请等待一分钟后重试。",
            retryable=True,
        )


def _save_upload(work_dir: Path) -> Path:
    upload = request.files.get("input_file")
    if upload is None or not upload.filename:
        raise ApiRequestError("E001", "请以 input_file 上传 md/docx/xlsx/pptx 文件。", status=400)
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in ALLOWED_INPUT_SUFFIXES:
        raise ApiRequestError("E003", "输入文件只支持 md/docx/xlsx/pptx。", status=400)
    path = work_dir / f"input{suffix}"
    _stream_upload(upload, path, max_bytes=MAX_INPUT_UPLOAD_BYTES, label="输入文件")
    return path


def _save_template_upload(work_dir: Path, target: TargetKind) -> Path | None:
    upload = request.files.get("template_file")
    if upload is None or not upload.filename:
        return None
    if target != "deck":
        raise ApiRequestError(
            "E001",
            "template_file 仅支持 deck 生成。",
            status=400,
            loc="template_file",
            suggestion="请切换为 PPT 汇报，或移除模板后生成 Word。",
        )
    if Path(upload.filename).suffix.lower() != ".pptx":
        raise ApiRequestError(
            "E003",
            "模板仅支持 .pptx 文件。",
            status=400,
            loc="template_file",
            suggestion="请在 PowerPoint 中另存为不含宏的 .pptx 后重新上传。",
        )
    path = work_dir / "template.pptx"
    _stream_upload(upload, path, max_bytes=MAX_TEMPLATE_UPLOAD_BYTES, label="模板文件")
    try:
        validate_template_package(path)
    except TemplateInputError as exc:
        raise ApiRequestError(
            exc.code,
            exc.message,
            status=400,
            loc=exc.loc,
            suggestion=_template_input_suggestion(exc),
        ) from exc
    return path


def _save_asset_uploads(work_dir: Path, target: TargetKind) -> Path | None:
    uploads = [upload for upload in request.files.getlist("asset_files") if upload and upload.filename]
    if not uploads:
        return None
    if target != "deck":
        raise ApiRequestError("A006", "asset_files 仅支持 deck 生成。", status=400)
    if len(uploads) > MAX_ASSET_UPLOADS:
        raise ApiRequestError("A003", f"图片数量超过 {MAX_ASSET_UPLOADS} 张限制。", status=413)
    raw_dir = work_dir / "asset_uploads"
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    total_bytes = 0
    allowed = {".png", ".jpg", ".jpeg", ".webp"}
    for index, upload in enumerate(uploads, start=1):
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in allowed:
            raise ApiRequestError("A001", "图片只支持 PNG、JPEG 或 WebP。", status=400)
        path = raw_dir / f"asset-{index:03d}{suffix}"
        total_bytes += _stream_upload(upload, path, max_bytes=MAX_ASSET_UPLOAD_BYTES, label=f"图片 {index}")
        if total_bytes > MAX_ASSET_TOTAL_BYTES:
            raise ApiRequestError("A003", "图片总大小超过 100 MB 限制。", status=413)
        paths.append(path)
    asset_dir = work_dir / "assets"
    try:
        normalize_assets(paths, asset_dir, source_type="upload")
    except AssetError as exc:
        raise ApiRequestError(exc.code, exc.message, status=400 if exc.code != "A003" else 413) from exc
    return asset_dir / "asset_manifest.json"


def _stream_upload(upload, path: Path, *, max_bytes: int, label: str) -> int:
    written = 0
    too_large = False
    try:
        with path.open("wb") as handle:
            while chunk := upload.stream.read(UPLOAD_CHUNK_BYTES):
                written += len(chunk)
                if written > max_bytes:
                    too_large = True
                    break
                handle.write(chunk)
    except OSError as exc:
        path.unlink(missing_ok=True)
        raise ApiRequestError("E001", f"{label}保存失败。", status=500) from exc
    if too_large:
        path.unlink(missing_ok=True)
        limit = f"{max_bytes // (1024 * 1024)} MB" if max_bytes >= 1024 * 1024 else f"{max_bytes} B"
        raise ApiRequestError("E004", f"{label}超过 {limit} 限制。", status=413)
    return written


def _ensure_disk_capacity(root: Path) -> None:
    request_bytes = max(int(request.content_length or 0), 0)
    required = MIN_FREE_DISK_BYTES + request_bytes * REQUEST_WORKING_SPACE_MULTIPLIER
    try:
        free = shutil.disk_usage(root).free
    except OSError as exc:
        raise ApiRequestError(
            "E004",
            "无法确认任务目录的可用磁盘空间。",
            status=503,
            loc="work_dir",
            suggestion="请检查输出目录权限和磁盘状态后重试。",
            retryable=True,
        ) from exc
    if free < required:
        raise ApiRequestError(
            "E004",
            "可用磁盘空间不足，未创建任务。",
            status=507,
            loc="work_dir",
            suggestion="请清理输出目录或释放磁盘空间后重试。",
            retryable=True,
        )


def _target_from_form() -> TargetKind:
    target = request.form.get("type", "").strip()
    if target not in {"word", "deck"}:
        raise ApiRequestError("E001", "type 只支持 word 或 deck。", status=400)
    return target  # type: ignore[return-value]


def _depth_from_form(target: TargetKind) -> Depth | None:
    raw = request.form.get("depth", "").strip()
    if not raw:
        return None
    if target != "deck":
        raise ApiRequestError("E001", "depth 仅支持 deck 生成。", status=400)
    if raw not in {"概览", "标准", "详细"}:
        raise ApiRequestError("E001", "depth 只支持 概览、标准 或 详细。", status=400)
    return raw  # type: ignore[return-value]


def _theme_from_form(target: TargetKind) -> str:
    raw = request.form.get("theme", "").strip()
    if not raw:
        return "hw_v1"
    if target != "deck":
        raise ApiRequestError("E001", "theme 仅支持 deck 生成。", status=400)
    if raw not in THEME_REGISTRY:
        available = ", ".join(sorted(THEME_REGISTRY))
        raise ApiRequestError("E001", f"theme 只支持 {available}。", status=400)
    return raw


def _preflight_generator_environment(manager: GeneratorManager, *, target: str) -> None:
    """Fail fast before queueing when the active generator cannot run locally.

    Mirrors open-kimi-ppt's step0 (check prerequisites, stop early with a clear
    message): a missing NGA CLI binary should surface at submit time, not when
    the job reaches the generating stage.
    """
    snapshot = manager.snapshot()
    if snapshot.name != "nga":
        return
    config = snapshot.generator.config if hasattr(snapshot.generator, "config") else None
    if not isinstance(config, NgaCliConfig):
        return
    cli_path = config.cli_path
    resolved = Path(cli_path)
    if resolved.is_absolute():
        available = resolved.is_file()
    else:
        available = shutil.which(cli_path) is not None
    if not available:
        raise ApiRequestError(
            "E010",
            f"NGA 命令行未找到：{cli_path}。",
            status=400,
            stage="preflight",
            loc="generator",
            suggestion="请确认已安装 NGA 并将命令加入 PATH，或在设置中填写正确的 CLI 路径。",
            retryable=False,
        )
    if sys.platform == "win32" and target == "deck":
        # DeckIR prompts (~58 KB, schema alone ~52 KB) always exceed the
        # 32767-character Windows CreateProcess command-line limit, so a deck
        # job via the CLI transport can never succeed on Windows (WinError 206).
        raise ApiRequestError(
            "E010",
            "NGA 命令行在 Windows 上无法传输 PPT 生成所需的超长请求。",
            status=400,
            stage="preflight",
            loc="generator",
            suggestion="Windows 命令行长度上限无法承载 DeckIR 请求；请改用 NGA HTTP 服务，或切换 Stub 生成器。",
            retryable=False,
        )


def _run_job(*, job_id: str, input_path: Path, generator: IRTextGenerator, jobs: JobStore) -> None:
    job = jobs.get(job_id)
    if job is None:
        return
    try:
        _execute_job(job, input_path, generator, jobs)
    except JobAborted:
        return
    except Exception as exc:
        _handle_job_failure(job, jobs, exc)


def _execute_job(job: ApiJob, input_path: Path, generator: IRTextGenerator, jobs: JobStore) -> None:
    if not jobs.update(job.job_id, status="running", stage="parsing", progress_percent=10):
        return
    document = parse_file(input_path)
    (job.work_dir / "document_ir.json").write_text(document.model_dump_json(indent=2) + "\n", encoding="utf-8")

    embedded = extract_office_image_files(input_path, job.work_dir / "document_asset_raw")
    if embedded:
        asset_dir = job.work_dir / "assets"
        normalize_assets(
            embedded,
            asset_dir,
            source_type="document",
            append=job.asset_manifest_path is not None,
        )
        if not jobs.update(job.job_id, asset_manifest_path=asset_dir / "asset_manifest.json"):
            return

    if not jobs.update(job.job_id, stage="generating", progress_percent=40):
        return
    artifact, report_payload, manifest = _generate_artifact(job, document, generator, jobs)
    _cleanup_sensitive_job_files(job, keep_artifact=True)
    jobs.update(
        job.job_id,
        status="done",
        stage="done",
        progress_percent=100,
        artifact_path=artifact,
        report=report_payload,
        manifest=manifest,
        template_path=None,
    )


def _handle_job_failure(job: ApiJob, jobs: JobStore, exc: Exception) -> None:
    if isinstance(exc, ApiValidationError):
        _fail_job(
            job,
            jobs,
            code="D001",
            stage="validation_failed",
            retryable=True,
            message="生成的 IR 未通过校验。",
            suggestion="请检查输入资料后重试；若持续失败，请下载失败报告并提供支持编号。",
            items=exc.items,
        )
    elif isinstance(exc, NgaGeneratorError):
        _fail_job(
            job,
            jobs,
            code=exc.code,
            stage="generating",
            retryable=exc.retryable,
            message=_generator_error_message(exc),
            suggestion=_generator_error_suggestion(exc),
            loc="generator",
        )
    elif isinstance(exc, TimeoutError):
        _fail_job(
            job,
            jobs,
            code="E002",
            stage=job.stage,
            retryable=True,
            message="内容生成服务响应超时。",
            suggestion="请稍后重试；若持续失败，请下载失败报告并提供支持编号。",
        )
    elif isinstance(exc, TemplateInputError):
        _fail_job(
            job,
            jobs,
            code=exc.code,
            stage=job.stage,
            retryable=False,
            message="模板或模板渲染结果未通过安全校验。",
            suggestion="请更换合法 .pptx 模板后重试。",
            loc=exc.loc,
        )
    elif isinstance(exc, AssetError):
        _fail_job(
            job,
            jobs,
            code=exc.code,
            stage=job.stage,
            retryable=False,
            message="图片资产未通过安全校验或引用无法解析。",
            suggestion="请检查图片格式、大小和引用后重试。",
            loc=exc.loc,
        )
    else:
        message, suggestion, retryable = _unexpected_job_failure(job.stage)
        _fail_job(
            job,
            jobs,
            code="E001",
            stage=job.stage,
            retryable=retryable,
            message=message,
            suggestion=suggestion,
        )


def _unexpected_job_failure(stage: str) -> tuple[str, str, bool]:
    if stage == "generating":
        return (
            "内容生成服务未完成响应。",
            "请稍后重试；若持续失败，请下载失败报告并提供支持编号。",
            True,
        )
    if stage == "parsing":
        return (
            "源文件无法解析。",
            "请确认文件未损坏、扩展名与实际格式一致后重试。",
            False,
        )
    return (
        "任务执行失败。",
        "请检查输入或模板后重试；若持续失败，请下载失败报告并提供支持编号。",
        False,
    )


def _fail_job(
    job: ApiJob,
    jobs: JobStore,
    *,
    code: str,
    stage: str,
    retryable: bool,
    message: str,
    suggestion: str,
    loc: str | None = None,
    items: list[dict[str, str]] | None = None,
    terminal_status: Literal["failed", "canceled"] = "failed",
) -> None:
    current = jobs.get(job.job_id)
    if current is None or current.status in TERMINAL_JOB_STATUSES:
        return
    envelope = FailureEnvelope(
        code=code,
        stage=stage,
        retryable=retryable,
        message=_safe_text(message),
        suggestion=_safe_text(suggestion),
        support_id=_support_id(job.job_id),
        loc=_safe_text(loc) if loc else None,
        items=_safe_validation_items(items or []),
    )
    error = envelope.model_dump(mode="json", exclude_none=True, exclude={"items"} if not envelope.items else set())

    failure_path = _write_failure_report(job, error)
    assets = dict(job.assets)
    assets["failure-report"] = failure_path
    _cleanup_sensitive_job_files(job)
    jobs.update(
        job.job_id,
        status=terminal_status,
        stage=stage,
        progress_percent=100,
        error=error,
        assets=assets,
        template_path=None,
    )


def _support_id(job_id: str) -> str:
    digest = sha256(job_id.encode("utf-8")).hexdigest()[:12].upper()
    return f"SUP-{digest}"


def _safe_validation_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "level": _safe_text(str(item.get("level", "Error"))),
            "code": _safe_text(str(item.get("code", "D001"))),
            "loc": _safe_text(str(item.get("loc", "<root>"))),
            "message": "IR 校验失败。",
            "suggestion": "请根据错误码和定位修正 IR 后重试。",
        }
        for item in items[:20]
    ]


def _safe_text(value: str, *, limit: int = 500) -> str:
    normalized = " ".join(value.replace("\x00", "").split())
    return normalized[:limit]


def _write_failure_report(job: ApiJob, error: dict[str, Any]) -> Path:
    path = job.work_dir / "failure_report.json"
    payload = {
        "failure_report_version": "1.0",
        "job": {
            "support_id": error["support_id"],
            "type": job.target,
            "depth": job.depth,
            "generator": {
                "name": job.generator_name,
                "revision": job.generator_revision,
            },
            "stage": error["stage"],
        },
        "error": error,
        "privacy": {
            "contains_raw_input": False,
            "contains_prompt": False,
            "contains_stack_trace": False,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _job_state(job: ApiJob) -> JobState:
    error = FailureEnvelope.model_validate(job.error) if job.error is not None else None
    return JobState(
        job_id=job.job_id,
        target=job.target,
        depth=job.depth,
        generator_name=job.generator_name,
        generator_revision=job.generator_revision,
        generator_mode=job.generator_mode,
        generator_fallback=job.generator_fallback,
        status=job.status,
        stage=job.stage,
        progress_percent=job.progress_percent,
        error=error,
        artifact_path=_relative_job_path(job.work_dir, job.artifact_path),
        report=job.report,
        manifest=job.manifest,
        template_path=_relative_job_path(job.work_dir, job.template_path),
        asset_manifest_path=_relative_job_path(job.work_dir, job.asset_manifest_path),
        assets={name: _relative_job_path(job.work_dir, path) for name, path in job.assets.items()},
        template_summary=job.template_summary,
        idempotency_key=job.idempotency_key,
        created_at=job.created_at,
        updated_at=job.updated_at,
        expires_at=job.expires_at,
    )


def _api_job_from_state(work_dir: Path, state: JobState) -> ApiJob:
    return ApiJob(
        job_id=state.job_id,
        target=state.target,
        depth=state.depth,
        work_dir=work_dir.resolve(),
        generator_name=state.generator_name,
        generator_revision=state.generator_revision,
        status=state.status,
        stage=state.stage,
        progress_percent=state.progress_percent,
        error=state.error.model_dump(mode="json", exclude_none=True) if state.error is not None else None,
        artifact_path=_resolve_job_path(work_dir, state.artifact_path),
        report=state.report,
        manifest=state.manifest,
        template_path=_resolve_job_path(work_dir, state.template_path),
        asset_manifest_path=_resolve_job_path(work_dir, state.asset_manifest_path),
        assets={name: _resolve_job_path(work_dir, path) for name, path in state.assets.items()},
        template_summary=state.template_summary,
        idempotency_key=state.idempotency_key,
        created_at=state.created_at,
        updated_at=state.updated_at,
        expires_at=state.expires_at,
    )


def _relative_job_path(work_dir: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(work_dir.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("job state path leaves the job directory") from exc


def _resolve_job_path(work_dir: Path, relative: str | None) -> Path | None:
    if relative is None:
        return None
    candidate = (work_dir / Path(relative)).resolve()
    try:
        candidate.relative_to(work_dir.resolve())
    except ValueError as exc:
        raise ValueError("job state path leaves the job directory") from exc
    return candidate


def _recover_interrupted_jobs(jobs: JobStore) -> None:
    for job in jobs.interrupted():
        _fail_job(
            job,
            jobs,
            code="E015",
            stage="interrupted",
            retryable=True,
            message="服务重启前任务未正常结束。",
            suggestion="请重新提交任务；若持续失败，请提供支持编号。",
        )


def _cleanup_sensitive_job_files(job: ApiJob, *, keep_artifact: bool = False) -> None:
    work_dir = job.work_dir.resolve()
    for path in list(work_dir.glob("input.*")) + [
        work_dir / "template.pptx",
        work_dir / "document_ir.json",
        work_dir / "prompt.txt",
        work_dir / "raw_ir.txt",
        work_dir / "generation_manifest.json",
        *([] if keep_artifact else [work_dir / "word.docx", work_dir / "deck.pptx"]),
    ]:
        try:
            if path.resolve().parent == work_dir:
                path.unlink(missing_ok=True)
        except OSError:
            continue
    for directory in [
        work_dir / "asset_uploads",
        work_dir / "document_asset_raw",
        work_dir / "prompts",
        work_dir / "assets" / "normalized",
    ]:
        try:
            resolved = directory.resolve()
            resolved.relative_to(work_dir)
        except (OSError, ValueError):
            continue
        if resolved.is_dir():
            shutil.rmtree(resolved, ignore_errors=True)


def _remove_job_directory(root: Path, work_dir: Path) -> None:
    resolved_root = root.resolve()
    resolved = work_dir.resolve()
    if resolved.parent != resolved_root or not JOB_DIRECTORY_RE.fullmatch(resolved.name):
        return
    shutil.rmtree(resolved, ignore_errors=True)


def _generate_artifact(
    job: ApiJob,
    document: DocumentIR,
    generator: IRTextGenerator,
    jobs: JobStore,
) -> tuple[Path, dict[str, Any], dict[str, Any] | None]:
    try:
        return _generate_artifact_with(generator, job, document, jobs)
    except NgaGeneratorError as exc:
        if not (job.generator_mode == "auto" and job.generator_name == "nga"):
            raise
        jobs.update(
            job.job_id,
            generator_fallback=True,
            stage="falling_back_to_stub",
            progress_percent=35,
        )
        fallback = StubGenerator()
        artifact, report_payload, manifest = _generate_artifact_with(
            fallback,
            job,
            document,
            jobs,
            fallback_reason=exc.code,
        )
        manifest = _record_fallback_manifest(job, exc.code, manifest)
        return artifact, report_payload, manifest


def _record_fallback_manifest(job: ApiJob, reason: str, manifest: dict[str, Any] | None) -> dict[str, Any]:
    fallback_payload = {
        "generator": {
            "requested": {"name": job.generator_name, "revision": job.generator_revision},
            "used": {"name": "stub", "revision": 0},
            "fallback": True,
            "fallback_reason": reason,
        }
    }
    if manifest is None:
        manifest = {}
    manifest.update(fallback_payload)
    return manifest


def _generate_artifact_with(
    generator: IRTextGenerator,
    job: ApiJob,
    document: DocumentIR,
    jobs: JobStore,
    *,
    fallback_reason: str | None = None,
) -> tuple[Path, dict[str, Any], dict[str, Any] | None]:
    context = _prepare_artifact_context(job, document, generator, jobs)
    if job.target == "deck" and job.depth is not None:
        return _generate_depth_deck_artifact(context)
    return _generate_single_artifact(context)


@dataclass
class _ArtifactContext:
    job: ApiJob
    document: DocumentIR
    generator: IRTextGenerator
    jobs: JobStore
    asset_registry: AssetRegistry | None
    asset_manifest: Any | None
    visual_plan: Any | None
    visual_assets: dict[str, Path]


def _prepare_artifact_context(
    job: ApiJob,
    document: DocumentIR,
    generator: IRTextGenerator,
    jobs: JobStore,
) -> _ArtifactContext:
    asset_registry: AssetRegistry | None = None
    asset_manifest = None
    if job.asset_manifest_path is not None:
        jobs.update(job.job_id, stage="normalizing_assets", progress_percent=22)
        asset_registry = load_asset_manifest(job.asset_manifest_path)
        asset_manifest = asset_registry.manifest
    visual_plan = None
    visual_assets: dict[str, Path] = {}
    if job.target == "deck":
        jobs.update(job.job_id, stage="planning_visuals", progress_percent=30)
        visual_plan = build_visual_plan(document, asset_manifest)
        visual_plan_path = job.work_dir / "visual_plan.json"
        visual_plan_path.write_text(visual_plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
        visual_assets["visual-plan"] = visual_plan_path
        if job.asset_manifest_path is not None:
            visual_assets["asset-manifest"] = job.asset_manifest_path
    return _ArtifactContext(
        job=job,
        document=document,
        generator=generator,
        jobs=jobs,
        asset_registry=asset_registry,
        asset_manifest=asset_manifest,
        visual_plan=visual_plan,
        visual_assets=visual_assets,
    )


def _generate_depth_deck_artifact(
    context: _ArtifactContext,
) -> tuple[Path, dict[str, Any], dict[str, Any] | None]:
    job = context.job
    attempt = generate_deck(
        context.document,
        generator=context.generator,
        options=GenerationOptions(depth=job.depth, theme=job.theme),
        visual_plan=context.visual_plan,
        asset_manifest=context.asset_manifest,
    )
    _ensure_job_active(job, context.jobs)
    _write_deck_attempt(job.work_dir, attempt)
    if not attempt.validation.ok or attempt.validation.value is None:
        raise ApiValidationError(_validation_items(attempt.validation))
    deck = attempt.validation.value
    selection_path = _write_visual_selection(job, context.visual_plan, deck)
    context.visual_assets["visual-selection-audit"] = selection_path
    artifact, profile, template_assets, template_summary = _render_deck(
        job,
        deck,
        context.jobs,
        asset_registry=context.asset_registry,
    )
    if context.asset_registry is not None:
        context.visual_assets["asset-usage-audit"] = job.work_dir / "asset_usage_audit.json"
    context.jobs.update(job.job_id, stage="linting", progress_percent=90)
    report = check_pptx(artifact, classification=deck.meta.classification, theme_name=deck.meta.theme, template_profile=profile)
    write_reports(report, job.work_dir)
    context.jobs.update(
        job.job_id,
        assets={
            **context.visual_assets,
            **template_assets,
            "lint": job.work_dir / "report.json",
            "deck-ir": job.work_dir / "deck_ir.json",
        },
        template_summary=template_summary,
    )
    return artifact, report.to_dict(), attempt.manifest()


def _generate_single_artifact(
    context: _ArtifactContext,
) -> tuple[Path, dict[str, Any], dict[str, Any] | None]:
    job = context.job
    prompt = build_prompt(
        kind=job.target,
        context=context.document,
        visual_plan=context.visual_plan,
        asset_manifest=context.asset_manifest,
    )
    (job.work_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    generator_target = "word_ir" if job.target == "word" else "deck_ir"
    raw = context.generator.generate(prompt, target=generator_target)
    _ensure_job_active(job, context.jobs)
    (job.work_dir / "raw_ir.txt").write_text(raw.strip() + "\n", encoding="utf-8")
    validation = repair_ir_text(raw, target=generator_target, generator=context.generator)
    _ensure_job_active(job, context.jobs)
    if not validation.ok or validation.value is None:
        raise ApiValidationError(_validation_items(validation))

    context.jobs.update(job.job_id, stage="rendering", progress_percent=75)
    if job.target == "word":
        artifact = render_word_ir(validation.value, job.work_dir / "word.docx")
        context.jobs.update(job.job_id, stage="linting", progress_percent=90)
        report = check_docx(artifact, classification=validation.value.meta.classification)
        write_docx_reports(report, job.work_dir)
    else:
        selection_path = _write_visual_selection(job, context.visual_plan, validation.value)
        context.visual_assets["visual-selection-audit"] = selection_path
        artifact, profile, template_assets, template_summary = _render_deck(
            job,
            validation.value,
            context.jobs,
            asset_registry=context.asset_registry,
        )
        if context.asset_registry is not None:
            context.visual_assets["asset-usage-audit"] = job.work_dir / "asset_usage_audit.json"
        context.jobs.update(job.job_id, stage="linting", progress_percent=90)
        report = check_pptx(
            artifact,
            classification=validation.value.meta.classification,
            theme_name=validation.value.meta.theme,
            template_profile=profile,
        )
        write_reports(report, job.work_dir)
        context.jobs.update(
            job.job_id,
            assets={
            **context.visual_assets,
            **template_assets,
            "lint": job.work_dir / "report.json",
            "deck-ir": job.work_dir / "deck_ir.json",
        },
            template_summary=template_summary,
        )
    return artifact, report.to_dict(), None


def _ensure_job_active(job: ApiJob, jobs: JobStore) -> None:
    current = jobs.get(job.job_id)
    if current is None or current.status in TERMINAL_JOB_STATUSES:
        raise JobAborted()


def _render_deck(job: ApiJob, deck, jobs: JobStore, *, asset_registry: AssetRegistry | None = None):
    if job.template_path is None:
        jobs.update(job.job_id, stage="rendering", progress_percent=75)
        return render_deck_ir(deck, job.work_dir / "deck.pptx", asset_registry=asset_registry), None, {}, None
    jobs.update(job.job_id, stage="profiling_template", progress_percent=58)
    profile = extract_template_profile(job.template_path)
    jobs.update(job.job_id, stage="planning_template", progress_percent=66)
    plan = build_template_plan(deck, profile)
    jobs.update(job.job_id, stage="rendering", progress_percent=75)
    result = render_deck_ir_with_template(
        deck,
        job.template_path,
        job.work_dir / "deck.pptx",
        audit_dir=job.work_dir,
        profile=profile,
        plan=plan,
        asset_registry=asset_registry,
    )
    jobs.update(job.job_id, stage="validating_package", progress_percent=86)
    package_report = validate_pptx_package(result.artifact_path)
    if not package_report["pass"]:
        raise TemplateInputError("E003", "output", package_report["errors"][0])
    assets = {
        "profile": result.profile_path,
        "plan": result.plan_path,
        "structure": result.structure_json_path,
        "replacement-audit": result.replacement_audit_path,
        "package-report": result.package_report_path,
    }
    summary = {
        "mode": "template",
        "filename": job.template_path.name,
        "prototype_replace": sum(slide.strategy == "prototype_replace" for slide in plan.slides),
        "master_redraw": sum(slide.strategy == "master_redraw" for slide in plan.slides),
        "warnings": len(plan.warnings),
    }
    return result.artifact_path, profile, assets, summary


def _write_visual_selection(job: ApiJob, visual_plan, deck) -> Path:
    if visual_plan is None:
        raise RuntimeError("deck generation requires a VisualPlan")
    audit = audit_visual_selection(visual_plan, deck)
    path = job.work_dir / "visual_selection_audit.json"
    path.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def _write_deck_attempt(work_dir: Path, attempt) -> None:
    prompts_dir = work_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for name, prompt in attempt.prompts.items():
        (prompts_dir / name).write_text(prompt, encoding="utf-8")
    (work_dir / "generation_manifest.json").write_text(
        json.dumps(attempt.manifest(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (work_dir / "raw_ir.txt").write_text(attempt.raw_text.strip() + "\n", encoding="utf-8")
    if attempt.validation.ok and attempt.validation.value is not None:
        (work_dir / "deck_ir.json").write_text(
            attempt.validation.value.model_dump_json(indent=2, by_alias=True) + "\n", encoding="utf-8"
        )


def _validation_items(result: ValidationResult) -> list[dict[str, str]]:
    return [
        {
            "level": item.level,
            "code": item.code,
            "loc": item.loc or "<root>",
            "message": item.message,
            "suggestion": item.suggestion or "",
        }
        for item in result.errors + result.warnings + result.infos
    ]


@dataclass
class ApiRequestError(Exception):
    code: str
    message: str
    status: int
    loc: str | None = None
    suggestion: str | None = None
    retryable: bool = False
    stage: str = "request_validation"


@dataclass
class ApiValidationError(Exception):
    items: list[dict[str, str]]


class JobAborted(Exception):
    """Internal control flow used after cancellation or timeout."""


def _validation_error(result: ValidationResult):
    return _error_response(
        "D001",
        "分析结果未通过校验。",
        status=422,
        stage="validating_analysis",
        suggestion="请检查输入内容后重试；若持续失败，请提供支持编号。",
        retryable=True,
        items=_validation_items(result),
    )


def _error_response(
    code: str,
    message: str,
    *,
    status: int,
    stage: str = "request_validation",
    loc: str | None = None,
    suggestion: str | None = None,
    retryable: bool | None = None,
    support_id: str | None = None,
    items: list[dict[str, str]] | None = None,
):
    envelope = FailureEnvelope(
        code=code,
        stage=stage,
        retryable=bool(retryable),
        message=_safe_text(message),
        suggestion=_safe_text(suggestion or _default_error_suggestion(status)),
        support_id=support_id or _support_id(uuid4().hex),
        loc=_safe_text(loc) if loc is not None else None,
        items=_safe_validation_items(items or []),
    )
    error = envelope.model_dump(mode="json", exclude_none=True, exclude={"items"} if not envelope.items else set())
    return jsonify({"error": error}), status


def _api_request_error_response(exc: ApiRequestError):
    return _error_response(
        exc.code,
        exc.message,
        status=exc.status,
        stage=exc.stage,
        loc=exc.loc,
        suggestion=exc.suggestion,
        retryable=exc.retryable,
    )


def _generator_error_response(
    exc: NgaGeneratorError,
    *,
    stage: str,
    conflict: bool = False,
):
    status = {
        "E010": 400,
        "E011": 401,
        "E012": 503,
        "E013": 429 if exc.http_status == 429 else 503,
        "E014": 502,
    }[exc.code]
    if conflict and exc.code == "E010":
        status = 409
    return _error_response(
        exc.code,
        _generator_error_message(exc),
        status=status,
        stage=stage,
        loc="generator",
        suggestion=_generator_error_suggestion(exc),
        retryable=exc.retryable,
    )


def _generator_error_message(exc: NgaGeneratorError) -> str:
    return {
        "E010": "NGA 配置无效或尚未完成连接测试。",
        "E011": "NGA 鉴权失败。",
        "E012": "无法连接 NGA，或 TLS 校验失败。",
        "E013": "NGA 已限流或服务暂时不可用。",
        "E014": "NGA 返回内容无法安全解析。",
    }[exc.code]


def _generator_error_suggestion(exc: NgaGeneratorError) -> str:
    return {
        "E010": "请在设置中检查地址、模型、凭据和 TLS 配置，并先通过连接测试。",
        "E011": "请更新 NGA Token 后重新测试连接。",
        "E012": "请检查内网连通性、证书和网关地址后重试。",
        "E013": "请等待限流窗口或服务恢复后重试。",
        "E014": "请确认网关兼容 OpenAI Chat Completions，并返回 choices[0].message.content。",
    }[exc.code]


def _default_error_suggestion(status: int) -> str:
    if status == 404:
        return "请确认任务编号或下载链接后重试。"
    if status == 409:
        return "请等待任务完成后再下载。"
    if status == 413:
        return "请减少文件大小或数量后重试。"
    if status >= 500:
        return "请稍后重试；若持续失败，请提供支持编号。"
    return "请按接口要求修正输入后重试。"


def _template_input_suggestion(exc: TemplateInputError) -> str:
    if "不安全嵌入部件" in exc.message:
        return (
            "请在 PowerPoint 中删除所列页面的嵌入 Excel、Visio 或 OLE 对象；"
            "如只需保留外观，请先将对象转成 PNG 后重新插入。该问题不能通过重试解决。"
        )
    if "外部关系" in exc.message:
        return "请在 PowerPoint 中断开外部链接并将所需内容嵌入为普通图片或原生图形后重新上传。"
    return "请修复模板包，或在 PowerPoint 中另存为新的无宏 .pptx 后重新上传。"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local production workbench with Waitress.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5056)
    parser.add_argument("--work-dir", type=Path, default=Path("output") / "web_api")
    args = parser.parse_args(argv)
    if args.host != "127.0.0.1":
        parser.error("production workbench must bind to 127.0.0.1")
    app = create_api_app(work_dir=args.work_dir)
    from waitress import serve

    serve(app, host=args.host, port=args.port, threads=4, clear_untrusted_proxy_headers=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
