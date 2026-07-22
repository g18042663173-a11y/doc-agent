from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Literal
from uuid import uuid4

from flask import Flask, jsonify, request, send_file

from app.cli.parse import parse_file
from app.generation.analysis import build_analysis_prompt, measure_document, validate_analysis_text
from app.generation.depth import GenerationOptions, generate_deck
from app.generators.interface import IRTextGenerator
from app.generators.stub import StubGenerator
from app.ir.document_ir import DocumentIR
from app.ir.errors import ValidationResult
from app.ir.repair import repair_generated_text, repair_ir_text
from app.lint.docx_lint import check_docx, write_docx_reports
from app.lint.pptx_lint import check_pptx, write_reports
from app.prompting.builder import Depth, build_prompt
from app.rendering.docx_renderer import render_word_ir
from app.rendering.pptx_renderer import render_deck_ir


ALLOWED_INPUT_SUFFIXES = {".md", ".docx", ".xlsx", ".pptx"}
TargetKind = Literal["word", "deck"]
JobStatus = Literal["pending", "running", "done", "failed"]


@dataclass
class ApiJob:
    job_id: str
    target: TargetKind
    depth: Depth | None
    work_dir: Path
    status: JobStatus = "pending"
    stage: str = "queued"
    progress_percent: int = 0
    error: dict[str, Any] | None = None
    artifact_path: Path | None = None
    report: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None

    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": self.job_id,
            "type": self.target,
            "depth": self.depth,
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
        if self.status == "failed":
            payload["error"] = self.error
        return payload


@dataclass
class JobStore:
    _jobs: dict[str, ApiJob] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def create(self, *, target: TargetKind, depth: Depth | None, work_dir: Path) -> ApiJob:
        job = ApiJob(job_id=work_dir.name, target=target, depth=depth, work_dir=work_dir)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> ApiJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for field_name, value in changes.items():
                setattr(job, field_name, value)

    def payload(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return None if job is None else job.payload()


def create_api_app(*, work_dir: Path | None = None, generator: IRTextGenerator | None = None) -> Flask:
    """Create the independent JSON API layer used by the future frontend.

    The default is deliberately the deterministic stub. NGA remains an intranet
    adapter concern and is not selected or implemented by this Mac-side API.
    """

    app = Flask(__name__)
    root = (work_dir or Path("output") / "web_api").resolve()
    root.mkdir(parents=True, exist_ok=True)
    app.config["API_WORK_DIR"] = root
    app.config["API_GENERATOR"] = generator or StubGenerator()
    app.config["API_JOBS"] = JobStore()

    @app.post("/api/analyze")
    def analyze():
        try:
            input_path = _save_upload(_new_workspace(root, prefix="analysis"))
            document = parse_file(input_path)
            metrics = measure_document(document)
            raw = app.config["API_GENERATOR"].generate(
                build_analysis_prompt(document, metrics), target="analysis"
            )
            result = repair_generated_text(
                raw,
                target="analysis",
                generator=app.config["API_GENERATOR"],
                validator=lambda current: validate_analysis_text(
                    current,
                    expected_metrics=metrics,
                    expected_filename=document.source.filename,
                ),
            )
            if not result.ok or result.value is None:
                return _validation_error(result)
            return jsonify(result.value.model_dump(mode="json"))
        except ApiRequestError as exc:
            return _error_response(exc.code, exc.message, status=exc.status)
        except Exception as exc:
            return _error_response("E001", f"分析失败: {exc}", status=500)

    @app.post("/api/generate")
    def generate():
        try:
            target = _target_from_form()
            depth = _depth_from_form(target)
            job_dir = _new_workspace(root, prefix="job")
            input_path = _save_upload(job_dir)
        except ApiRequestError as exc:
            return _error_response(exc.code, exc.message, status=exc.status)

        jobs: JobStore = app.config["API_JOBS"]
        job = jobs.create(target=target, depth=depth, work_dir=job_dir)
        Thread(
            target=_run_job,
            kwargs={
                "job_id": job.job_id,
                "input_path": input_path,
                "generator": app.config["API_GENERATOR"],
                "jobs": jobs,
            },
            daemon=True,
            name=f"web-api-{job.job_id}",
        ).start()
        return jsonify(job.payload()), 202

    @app.get("/api/status/<job_id>")
    def status(job_id: str):
        jobs: JobStore = app.config["API_JOBS"]
        payload = jobs.payload(job_id)
        if payload is None:
            return _error_response("E001", "任务不存在。", status=404)
        return jsonify(payload)

    @app.get("/api/download/<job_id>")
    def download(job_id: str):
        jobs: JobStore = app.config["API_JOBS"]
        job = jobs.get(job_id)
        if job is None:
            return _error_response("E001", "任务不存在。", status=404)
        if job.status != "done" or job.artifact_path is None:
            return _error_response("E001", "任务尚未完成，暂无可下载产物。", status=409)
        if not job.artifact_path.is_file():
            return _error_response("E001", "任务产物不存在。", status=404)
        return send_file(job.artifact_path, as_attachment=True, download_name=job.artifact_path.name)

    return app


def _new_workspace(root: Path, *, prefix: str) -> Path:
    path = root / f"{prefix}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _save_upload(work_dir: Path) -> Path:
    upload = request.files.get("input_file")
    if upload is None or not upload.filename:
        raise ApiRequestError("E001", "请以 input_file 上传 md/docx/xlsx/pptx 文件。", status=400)
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in ALLOWED_INPUT_SUFFIXES:
        raise ApiRequestError("E003", "输入文件只支持 md/docx/xlsx/pptx。", status=400)
    path = work_dir / f"input{suffix}"
    upload.save(path)
    return path


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


def _run_job(*, job_id: str, input_path: Path, generator: IRTextGenerator, jobs: JobStore) -> None:
    job = jobs.get(job_id)
    if job is None:
        return
    try:
        jobs.update(job_id, status="running", stage="parsing", progress_percent=10)
        document = parse_file(input_path)
        (job.work_dir / "document_ir.json").write_text(document.model_dump_json(indent=2) + "\n", encoding="utf-8")

        jobs.update(job_id, stage="generating", progress_percent=40)
        artifact, report_payload, manifest = _generate_artifact(job, document, generator, jobs)
        jobs.update(
            job_id,
            status="done",
            stage="done",
            progress_percent=100,
            artifact_path=artifact,
            report=report_payload,
            manifest=manifest,
        )
    except ApiValidationError as exc:
        jobs.update(
            job_id,
            status="failed",
            stage="validation_failed",
            progress_percent=100,
            error={"code": "D001", "message": "生成的 IR 未通过校验。", "items": exc.items},
        )
    except Exception as exc:
        jobs.update(
            job_id,
            status="failed",
            stage="failed",
            progress_percent=100,
            error={"code": "E001", "message": f"生成失败: {exc}"},
        )


def _generate_artifact(
    job: ApiJob,
    document: DocumentIR,
    generator: IRTextGenerator,
    jobs: JobStore,
) -> tuple[Path, dict[str, Any], dict[str, Any] | None]:
    if job.target == "deck" and job.depth is not None:
        attempt = generate_deck(document, generator=generator, options=GenerationOptions(depth=job.depth))
        _write_deck_attempt(job.work_dir, attempt)
        if not attempt.validation.ok or attempt.validation.value is None:
            raise ApiValidationError(_validation_items(attempt.validation))
        deck = attempt.validation.value
        jobs.update(job.job_id, stage="rendering", progress_percent=75)
        artifact = render_deck_ir(deck, job.work_dir / "deck.pptx")
        jobs.update(job.job_id, stage="linting", progress_percent=90)
        report = check_pptx(artifact, classification=deck.meta.classification)
        write_reports(report, job.work_dir)
        return artifact, report.to_dict(), attempt.manifest()

    prompt = build_prompt(kind=job.target, context=document)
    (job.work_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    generator_target = "word_ir" if job.target == "word" else "deck_ir"
    raw = generator.generate(prompt, target=generator_target)
    (job.work_dir / "raw_ir.txt").write_text(raw.strip() + "\n", encoding="utf-8")
    validation = repair_ir_text(raw, target=generator_target, generator=generator)
    if not validation.ok or validation.value is None:
        raise ApiValidationError(_validation_items(validation))

    jobs.update(job.job_id, stage="rendering", progress_percent=75)
    if job.target == "word":
        artifact = render_word_ir(validation.value, job.work_dir / "word.docx")
        jobs.update(job.job_id, stage="linting", progress_percent=90)
        report = check_docx(artifact, classification=validation.value.meta.classification)
        write_docx_reports(report, job.work_dir)
    else:
        artifact = render_deck_ir(validation.value, job.work_dir / "deck.pptx")
        jobs.update(job.job_id, stage="linting", progress_percent=90)
        report = check_pptx(artifact, classification=validation.value.meta.classification)
        write_reports(report, job.work_dir)
    return artifact, report.to_dict(), None


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


@dataclass(frozen=True)
class ApiRequestError(Exception):
    code: str
    message: str
    status: int


@dataclass(frozen=True)
class ApiValidationError(Exception):
    items: list[dict[str, str]]


def _validation_error(result: ValidationResult):
    return jsonify({"error": {"code": "D001", "message": "分析结果未通过校验。", "items": _validation_items(result)}}), 422


def _error_response(code: str, message: str, *, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the stub-backed asynchronous JSON API for frontend development.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5056)
    parser.add_argument("--work-dir", type=Path, default=Path("output") / "web_api")
    args = parser.parse_args(argv)
    app = create_api_app(work_dir=args.work_dir)
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
