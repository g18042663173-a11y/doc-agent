from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from doc_agent.aicoding import AICodingPromptBuilder
from doc_agent.api.task_history import TaskHistoryManager, TaskMetadata
from doc_agent.colors.manager import ColorManager
from doc_agent.compliance.docx import WordComplianceChecker
from doc_agent.compliance.pptx import HuaweiPptxComplianceChecker
from doc_agent.config import get_settings, load_style_profile
from doc_agent.ir.schemas import DeckIR, WordIR
from doc_agent.parsers.router import ParserRouter
from doc_agent.renderers.docx_python_renderer import PythonDocxRenderer
from doc_agent.renderers.pptx_python_renderer import PythonPptxRenderer
from doc_agent.templates.manager import TemplateManager
from doc_agent.utils.json_utils import extract_json_from_text
from doc_agent.validators.output_validator import OutputValidator
from doc_agent.validators.word_validator import WordValidator


router = APIRouter(prefix="/api/aicoding", tags=["AICoding桥接"])


class PromptResponse(BaseModel):
    prompt: str
    target: Literal["docx", "pptx"]
    slides: int
    document_ir: dict[str, Any]
    source_summary: str


class ManualRenderRequest(BaseModel):
    target: Literal["docx", "pptx"]
    model_output: str | dict[str, Any]
    template_id: str | None = None
    color_scheme_id: str | None = None
    original_filename: str | None = None
    slides: int | None = None


class ManualRenderResponse(BaseModel):
    task_id: str
    status: str
    result: str
    compliance_report: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


@router.post("/prompt")
async def build_prompt(
    file: UploadFile = File(...),
    target: Literal["docx", "pptx"] = Form("docx"),
    slides: int = Form(8),
) -> PromptResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".md", ".docx", ".pptx", ".xlsx", ".xlsm"}:
        raise HTTPException(status_code=400, detail="仅支持 .md、.docx、.pptx、.xlsx、.xlsm 文件。")
    if slides < 1:
        raise HTTPException(status_code=400, detail="页数必须是正整数。")

    settings = get_settings()
    task_id = uuid.uuid4().hex
    upload_dir = settings.data_dir / "aicoding" / "uploads" / task_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    input_path = upload_dir / Path(file.filename or f"input{suffix}").name
    input_path.write_bytes(await file.read())

    try:
        document_ir = ParserRouter().parse(input_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"文件解析失败：{exc}") from exc

    prompt = AICodingPromptBuilder().build(document_ir, target, slides=slides)
    return PromptResponse(
        prompt=prompt,
        target=target,
        slides=slides,
        document_ir=document_ir.model_dump(mode="json"),
        source_summary=_source_summary(document_ir.model_dump(mode="json")),
    )


@router.post("/render")
async def render_manual_output(request: ManualRenderRequest) -> ManualRenderResponse:
    settings = get_settings()
    task_id = uuid.uuid4().hex
    history = TaskHistoryManager()
    metadata = TaskMetadata(
        original_filename=request.original_filename or "AICoding pasted JSON",
        source_type="aicoding",
        target=request.target,
        slides=request.slides,
        template_id=request.template_id,
        color_scheme_id=request.color_scheme_id,
    )
    history.create_task(task_id, "processing", 30, "校验 AICoding JSON", metadata)

    try:
        raw = _coerce_model_output(request.model_output)
        output_path = settings.output_dir / task_id / f"generated.{request.target}"
        style_profile = _style_profile(request.template_id, request.color_scheme_id)
        warnings: list[str] = []

        if request.target == "docx":
            word = WordIR.model_validate(raw)
            word, errors, warnings = WordValidator(style_profile).validate_and_fix(word)
            if errors:
                raise ValueError("; ".join(errors))
            result = PythonDocxRenderer(style_profile=style_profile).render(word.model_dump(mode="json"), output_path)
            report = WordComplianceChecker().check(result).model_dump(mode="json")
        else:
            deck = DeckIR.model_validate(raw)
            result = PythonPptxRenderer(style_profile=style_profile).render(deck.model_dump(mode="json"), output_path)
            report = HuaweiPptxComplianceChecker().check(result).model_dump(mode="json")

        output_errors = OutputValidator().validate(result, request.target)
        if output_errors:
            raise ValueError("; ".join(output_errors))
        history.update_task(task_id, "completed", 100, "AICoding 结果已生成", result=str(result), compliance_report=report)
        return ManualRenderResponse(
            task_id=task_id,
            status="completed",
            result=str(result),
            compliance_report=report,
            warnings=warnings,
        )
    except Exception as exc:
        history.update_task(
            task_id,
            "failed",
            0,
            "AICoding 结果处理失败",
            error=str(exc),
            error_type=exc.__class__.__name__,
            friendly_error=_friendly_error(exc),
        )
        raise HTTPException(status_code=400, detail=_friendly_error(exc)) from exc


def _coerce_model_output(output: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(output, dict):
        return output
    try:
        return extract_json_from_text(output)
    except ValueError as exc:
        raise ValueError("没有找到可解析的 JSON 对象，请确认 AICoding 输出只包含 JSON。") from exc


def _style_profile(template_id: str | None, color_scheme_id: str | None) -> dict[str, Any]:
    style = load_style_profile()
    if template_id:
        overrides = TemplateManager().style_overrides(template_id)
        if overrides.get("fonts"):
            style.setdefault("fonts", {}).update(overrides["fonts"])
        if overrides.get("colors"):
            style.setdefault("colors", {}).update(overrides["colors"])
        if overrides.get("slide_size"):
            style["slide_size"] = overrides["slide_size"]
    if color_scheme_id:
        style = ColorManager().apply_scheme_to_style(color_scheme_id, style)
    return style


def _source_summary(document_ir: dict[str, Any]) -> str:
    blocks = document_ir.get("blocks") or []
    return f"{document_ir.get('source_type', 'unknown')} · {len(blocks)} 个结构块 · {document_ir.get('title') or '未命名'}"


def _friendly_error(exc: Exception) -> str:
    message = str(exc)
    if "JSON" in message or "json" in message:
        return "AICoding 输出不是合法 JSON，请复制完整 JSON 对象后重试。"
    if "validation" in message.lower() or "validate" in message.lower():
        return "AICoding JSON 字段不符合目标 IR 规范，请按提示词要求重新生成。"
    if "table block is empty" in message:
        return "WordIR 表格块缺少表头或数据，请让 AICoding 补齐 table_headers/table_rows。"
    return f"AICoding 结果处理失败：{message}"
