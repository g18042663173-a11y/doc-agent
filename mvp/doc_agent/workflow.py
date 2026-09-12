from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional, TypedDict

from doc_agent.config import Settings, get_settings, normalize_ppt_renderer
from doc_agent.ir.schemas import DeckIR, DocumentIR, WordIR
from doc_agent.parsers.router import ParserRouter
from doc_agent.planners.deck_planner import DeckPlanner
from doc_agent.planners.word_planner import WordPlanner
from doc_agent.renderers.docx_python_renderer import PythonDocxRenderer
from doc_agent.renderers.huawei_skill_renderer import HuaweiSkillRenderer
from doc_agent.renderers.pptx_python_renderer import PythonPptxRenderer
from doc_agent.compliance.pptx import HuaweiPptxComplianceChecker
from doc_agent.compliance.docx import WordComplianceChecker
from doc_agent.validators.deck_validator import DeckValidator
from doc_agent.validators.output_validator import OutputValidator
from doc_agent.validators.word_validator import WordValidator


class WorkflowState(TypedDict):
    input_path: str
    target: Literal["pptx", "docx"]
    target_slide_count: int
    document_ir: Optional[dict[str, Any]]
    deck_ir: Optional[dict[str, Any]]
    word_ir: Optional[dict[str, Any]]
    output_path: Optional[str]
    runtime_settings: Any
    style_profile: Optional[dict[str, Any]]
    llm_provider: str
    ppt_renderer: str
    errors: list[str]
    warnings: list[str]
    compliance_report: Optional[dict[str, Any]]
    debug: dict[str, Any]


def initial_state(
    input_path: str | Path,
    target: Literal["pptx", "docx"],
    output_path: str | Path,
    target_slide_count: int = 8,
    settings: Settings | None = None,
    style_profile: dict[str, Any] | None = None,
) -> WorkflowState:
    active_settings = settings or get_settings()
    return {
        "input_path": str(input_path),
        "target": target,
        "target_slide_count": target_slide_count,
        "document_ir": None,
        "deck_ir": None,
        "word_ir": None,
        "output_path": str(output_path),
        "runtime_settings": active_settings,
        "style_profile": style_profile,
        "llm_provider": active_settings.llm_provider,
        "ppt_renderer": normalize_ppt_renderer(active_settings.ppt_renderer),
        "errors": [],
        "warnings": [],
        "compliance_report": None,
        "debug": {},
    }


def detect_file_type_node(state: WorkflowState) -> WorkflowState:
    state["debug"]["input_suffix"] = Path(state["input_path"]).suffix.lower()
    return state


def parse_document_node(state: WorkflowState) -> WorkflowState:
    try:
        document_ir = ParserRouter().parse(state["input_path"])
        state["document_ir"] = document_ir.model_dump(mode="json")
    except Exception as exc:
        state["errors"].append(f"parse_document_node failed: {exc}")
    return state


def generate_ir_node(state: WorkflowState) -> WorkflowState:
    if state["errors"]:
        return state
    try:
        document_ir = DocumentIR.model_validate(state["document_ir"])
        settings = state.get("runtime_settings") or get_settings()
        if state["target"] == "pptx":
            deck = DeckPlanner(settings=settings).plan(document_ir, state["target_slide_count"])
            state["deck_ir"] = deck.model_dump(mode="json")
        else:
            word = WordPlanner(settings=settings).plan(document_ir)
            state["word_ir"] = word.model_dump(mode="json")
    except Exception as exc:
        state["errors"].append(f"generate_ir_node failed: {exc}")
    return state


def validate_ir_node(state: WorkflowState) -> WorkflowState:
    if state["errors"]:
        return state
    try:
        if state["target"] == "pptx":
            deck = DeckIR.model_validate(state["deck_ir"])
            deck, errors, warnings = DeckValidator().validate_and_fix(deck)
            state["deck_ir"] = deck.model_dump(mode="json")
        else:
            word = WordIR.model_validate(state["word_ir"])
            word, errors, warnings = WordValidator().validate_and_fix(word)
            state["word_ir"] = word.model_dump(mode="json")
        state["errors"].extend(errors)
        state["warnings"].extend(warnings)
    except Exception as exc:
        state["errors"].append(f"validate_ir_node failed: {exc}")
    return state


def repair_ir_node(state: WorkflowState) -> WorkflowState:
    return state


def render_output_node(state: WorkflowState) -> WorkflowState:
    if state["errors"]:
        return state
    try:
        output_path = Path(state["output_path"] or "")
        if state["target"] == "pptx":
            if state["ppt_renderer"] == "stub":
                renderer = PythonPptxRenderer(style_profile=state.get("style_profile"))
            elif state["ppt_renderer"] == "hw_skill":
                renderer = HuaweiSkillRenderer()
            elif state["ppt_renderer"] == "presenton":
                raise RuntimeError("PPT_RENDERER=presenton is no longer supported. Use stub outside the intranet or hw_skill inside.")
            else:
                raise RuntimeError(f"Unsupported PPT_RENDERER: {state['ppt_renderer']}")
            result = renderer.render(state["deck_ir"] or {}, output_path)
        else:
            result = PythonDocxRenderer(style_profile=state.get("style_profile")).render(state["word_ir"] or {}, output_path)
        state["output_path"] = str(result)
    except Exception as exc:
        state["errors"].append(f"render_output_node failed: {exc}")
    return state


def validate_output_node(state: WorkflowState) -> WorkflowState:
    if state["errors"]:
        return state
    errors = OutputValidator().validate(state["output_path"] or "", state["target"])
    state["errors"].extend(errors)
    if errors:
        return state
    if state["target"] == "pptx":
        settings = state.get("runtime_settings") or get_settings()
        if settings.ppt_compliance_gate != "off":
            report = HuaweiPptxComplianceChecker().check(state["output_path"] or "")
            state["compliance_report"] = report.model_dump(mode="json")
            if report.items:
                state["warnings"].append(f"compliance score {report.score}: {report.summary}")
            if settings.ppt_compliance_gate == "error" and report.error_count > 0:
                state["errors"].append(f"Huawei compliance failed: {report.summary}")
    elif state["target"] == "docx":
        report = WordComplianceChecker().check(state["output_path"] or "")
        state["compliance_report"] = report.model_dump(mode="json")
        if report.items:
            state["warnings"].append(f"word format score {report.score}: {report.summary}")
    return state


def build_workflow_graph():
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    graph = StateGraph(WorkflowState)
    graph.add_node("detect_file_type", detect_file_type_node)
    graph.add_node("parse_document", parse_document_node)
    graph.add_node("generate_ir", generate_ir_node)
    graph.add_node("validate_ir", validate_ir_node)
    graph.add_node("repair_ir", repair_ir_node)
    graph.add_node("render_output", render_output_node)
    graph.add_node("validate_output", validate_output_node)
    graph.set_entry_point("detect_file_type")
    graph.add_edge("detect_file_type", "parse_document")
    graph.add_edge("parse_document", "generate_ir")
    graph.add_edge("generate_ir", "validate_ir")
    graph.add_edge("validate_ir", "repair_ir")
    graph.add_edge("repair_ir", "render_output")
    graph.add_edge("render_output", "validate_output")
    graph.add_edge("validate_output", END)
    return graph.compile()


def run_generate(
    input_path: str | Path,
    target: Literal["pptx", "docx"],
    output_path: str | Path,
    target_slide_count: int = 8,
    settings: Settings | None = None,
    style_profile: dict[str, Any] | None = None,
) -> Path:
    final_state = run_generate_state(input_path, target, output_path, target_slide_count, settings, style_profile)
    return Path(final_state["output_path"] or output_path)


def run_generate_state(
    input_path: str | Path,
    target: Literal["pptx", "docx"],
    output_path: str | Path,
    target_slide_count: int = 8,
    settings: Settings | None = None,
    style_profile: dict[str, Any] | None = None,
) -> WorkflowState:
    state = initial_state(input_path, target, output_path, target_slide_count, settings, style_profile)
    active_settings = state.get("runtime_settings") or get_settings()
    graph = build_workflow_graph() if active_settings.use_langgraph else None
    if graph is not None:
        final_state = graph.invoke(state)
    else:
        final_state = state
        for node in (
            detect_file_type_node,
            parse_document_node,
            generate_ir_node,
            validate_ir_node,
            repair_ir_node,
            render_output_node,
            validate_output_node,
        ):
            final_state = node(final_state)
    if final_state["errors"]:
        raise RuntimeError("; ".join(final_state["errors"]))
    return final_state
