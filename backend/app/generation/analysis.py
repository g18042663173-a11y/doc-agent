from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.ir.document_ir import DocumentIR
from app.ir.errors import ValidationItem, ValidationResult
from app.ir.shell import JsonExtractionError, extract_json_text


Depth = Literal["概览", "标准", "详细"]
ANALYSIS_MARKER = "[分析实测数据]"
DEPTH_ORDER: tuple[Depth, ...] = ("概览", "标准", "详细")


class AnalysisMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_count: int = Field(ge=0)
    max_heading_depth: int = Field(ge=0, le=6)
    table_count: int = Field(ge=0)
    character_count: int = Field(ge=0)


class PageTier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    depth: Depth
    min_pages: int = Field(ge=3, le=30)
    max_pages: int = Field(ge=3, le=30)
    coverage: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> "PageTier":
        if self.min_pages > self.max_pages:
            raise ValueError("min_pages must not exceed max_pages")
        return self


class AnalysisRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_version: Literal["1.0"]
    source_filename: str = Field(min_length=1)
    metrics: AnalysisMetrics
    tiers: list[PageTier] = Field(min_length=3, max_length=3)
    recommended_depth: Depth
    recommended_reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_tiers(self) -> "AnalysisRecommendation":
        if tuple(tier.depth for tier in self.tiers) != DEPTH_ORDER:
            raise ValueError("tiers must be ordered as 概览, 标准, 详细")
        for previous, current in zip(self.tiers, self.tiers[1:]):
            if previous.max_pages >= current.min_pages:
                raise ValueError("tier page ranges must increase without overlap")
        return self


def measure_document(document: DocumentIR) -> AnalysisMetrics:
    outline_depth = max((item.level for item in document.content.outline), default=0)
    return AnalysisMetrics(
        title_count=document.stats.headings,
        max_heading_depth=outline_depth,
        table_count=document.stats.tables,
        character_count=_content_character_count(document),
    )


def build_analysis_prompt(document: DocumentIR, metrics: AnalysisMetrics) -> str:
    measured = {
        "source_filename": document.source.filename,
        "metrics": metrics.model_dump(mode="json"),
    }
    structure_hints = _structure_hints(document)
    schema = AnalysisRecommendation.model_json_schema()
    return (
        "[任务] 根据文件解析后的实测规模，给出 PPT 页数/深度建议；本次不生成任何 IR 或 PPT。\n"
        "[输出纪律] 只输出一个完整合法 JSON 对象，不要 Markdown 围栏、解释或额外字段。\n"
        "[判断要求] 三档必须依次为概览、标准、详细，每档给不重叠的页数区间和一句覆盖说明；"
        "推荐理由必须引用实测标题数、层级、表格数或字数，不得修改实测数字。\n"
        "[档位基准] 概览约 6-8 页，只覆盖核心结论；标准约 10-12 页，覆盖主要章节和关键支撑；"
        "详细约 14-18 页，展开方法、架构、数据、权衡和适用条件。\n"
        f"{ANALYSIS_MARKER}\n{json.dumps(measured, ensure_ascii=False, sort_keys=True)}\n"
        f"[结构线索]\n{json.dumps(structure_hints, ensure_ascii=False, sort_keys=True)}\n"
        f"[独立轻量 Schema]\n{json.dumps(schema, ensure_ascii=False, sort_keys=True)}\n"
        "[最后自检] metrics 必须逐项复制实测数据；只给建议，不得输出 deck_ir/word_ir/document_ir。"
    )


def validate_analysis_text(
    raw: str,
    *,
    expected_metrics: AnalysisMetrics,
    expected_filename: str | None = None,
) -> ValidationResult[AnalysisRecommendation]:
    try:
        extracted = extract_json_text(raw)
        value = AnalysisRecommendation.model_validate_json(extracted)
    except JsonExtractionError as exc:
        return ValidationResult(value=None, errors=[_analysis_error("D001", "", f"建议 JSON 剥壳失败: {exc}")])
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ()))
        return ValidationResult(
            value=None,
            errors=[_analysis_error("D002", location, f"建议结构不合法: {first.get('msg', 'validation failed')}")],
        )
    if value.metrics != expected_metrics:
        return ValidationResult(
            value=None,
            errors=[_analysis_error("D004", "metrics", "AI 返回的文件规模与 parser 实测数据不一致")],
        )
    if expected_filename is not None and value.source_filename != expected_filename:
        return ValidationResult(
            value=None,
            errors=[_analysis_error("D004", "source_filename", "AI 返回的文件名与实测来源不一致")],
        )
    return ValidationResult(value=value)


def format_analysis(recommendation: AnalysisRecommendation) -> str:
    metrics = recommendation.metrics
    lines = [
        "文件规模摘要",
        (
            f"- {metrics.title_count} 个标题，结构深度 {metrics.max_heading_depth} 级，"
            f"{metrics.table_count} 张表，约 {metrics.character_count} 字"
        ),
        "三档建议",
    ]
    lines.extend(
        f"- {tier.depth}: {tier.min_pages}-{tier.max_pages} 页；{tier.coverage}" for tier in recommendation.tiers
    )
    lines.extend(
        [
            f"推荐: {recommendation.recommended_depth}",
            f"理由: {recommendation.recommended_reason}",
        ]
    )
    return "\n".join(lines)


def stub_analysis_payload(measured: dict[str, Any]) -> dict[str, Any]:
    metrics = AnalysisMetrics.model_validate(measured.get("metrics", {}))
    if metrics.title_count >= 20 or metrics.character_count >= 10000 or metrics.table_count >= 5:
        recommended: Depth = "详细"
    elif metrics.title_count >= 8 or metrics.character_count >= 3000 or metrics.table_count >= 2:
        recommended = "标准"
    else:
        recommended = "概览"
    reason = (
        f"实测有 {metrics.title_count} 个标题、{metrics.max_heading_depth} 级结构、"
        f"{metrics.table_count} 张表和约 {metrics.character_count} 字，{recommended}档与当前规模匹配。"
    )
    return {
        "analysis_version": "1.0",
        "source_filename": str(measured.get("source_filename") or "未知文件"),
        "metrics": metrics.model_dump(mode="json"),
        "tiers": [
            {"depth": "概览", "min_pages": 6, "max_pages": 8, "coverage": "核心结论和关键指标"},
            {"depth": "标准", "min_pages": 10, "max_pages": 12, "coverage": "主要章节、关键方法和数据支撑"},
            {"depth": "详细", "min_pages": 14, "max_pages": 18, "coverage": "方法、架构、数据、权衡和适用条件"},
        ],
        "recommended_depth": recommended,
        "recommended_reason": reason,
    }


def _content_character_count(document: DocumentIR) -> int:
    if document.source.format in {"md", "docx"}:
        payloads = [block.model_dump(mode="json") for block in document.content.blocks]
        return sum(_block_character_count(block) for block in payloads)
    if document.source.format == "xlsx":
        values: list[str] = []
        for sheet in document.content.sheets:
            values.append(sheet.name)
            values.extend(str(cell) for row in sheet.preview_rows for cell in row)
        return sum(len(value) for value in values)
    values = []
    for slide in document.content.slides:
        values.extend([slide.title or "", *slide.bodies, slide.notes or ""])
        for table in slide.tables:
            values.extend(_strings(table))
    return sum(len(value) for value in values)


def _block_character_count(block: dict[str, Any]) -> int:
    block_type = block.get("type")
    if block_type in {"heading", "paragraph"}:
        return len(str(block.get("text") or ""))
    if block_type in {"bullet_list", "numbered_list"}:
        return sum(len(str(item.get("text") or "")) for item in block.get("items", []))
    if block_type == "table":
        return sum(len(value) for value in _strings({"header": block.get("header", []), "rows": block.get("rows", [])}))
    if block_type == "image_placeholder":
        return len(str(block.get("caption") or ""))
    return 0


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in _strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _strings(child)]
    return []


def _structure_hints(document: DocumentIR) -> dict[str, Any]:
    if document.source.format in {"md", "docx"}:
        return {"outline": [item.model_dump(mode="json") for item in document.content.outline[:40]]}
    if document.source.format == "xlsx":
        return {"sheets": [sheet.name for sheet in document.content.sheets[:12]]}
    return {"slides": [slide.title or f"第{slide.index}页" for slide in document.content.slides[:30]]}


def _analysis_error(code: str, loc: str, message: str) -> ValidationItem:
    return ValidationItem(
        code=code,
        level="Error",
        loc=loc,
        message=message,
        suggestion="要求模型只输出独立建议 JSON，并保持 parser 实测数字不变。",
    )
