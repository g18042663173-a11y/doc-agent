from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from doc_agent.colors.manager import ColorManager
from doc_agent.config import Settings, get_settings, load_style_profile, normalize_llm_provider, normalize_ppt_renderer
from doc_agent.templates.manager import TemplateManager
from doc_agent.users.manager import UserManager
from doc_agent.workflow import run_generate_state

if TYPE_CHECKING:
    from doc_agent.api.task_history import TaskHistoryManager


TargetType = Literal["pptx", "docx"]


@dataclass(frozen=True)
class AgentRunRequest:
    input_path: Path
    target: TargetType
    output_path: Path
    slides: int = 8
    template_id: str | None = None
    color_scheme_id: str | None = None
    user_id: str | None = None
    profile_id: str | None = None


@dataclass(frozen=True)
class AgentRunContext:
    settings: Settings
    style_profile: dict[str, Any]
    profile_id: str | None = None


@dataclass(frozen=True)
class AgentRunResult:
    output_path: Path | None
    warnings: list[str]
    errors: list[str]
    compliance_report: dict[str, Any] | None
    debug: dict[str, Any]
    workflow_state: dict[str, Any]


class AgentRunner:
    def __init__(
        self,
        user_manager: UserManager | None = None,
        template_manager: TemplateManager | None = None,
        color_manager: ColorManager | None = None,
        task_history: "TaskHistoryManager | None" = None,
    ) -> None:
        self.user_manager = user_manager or UserManager()
        self.template_manager = template_manager or TemplateManager()
        self.color_manager = color_manager or ColorManager()
        if task_history is None:
            from doc_agent.api.task_history import TaskHistoryManager

            task_history = TaskHistoryManager()
        self.task_history = task_history

    def build_context(self, request: AgentRunRequest) -> AgentRunContext:
        profile_id = request.profile_id or request.user_id
        return AgentRunContext(
            settings=self._runtime_settings(profile_id),
            style_profile=self._style_profile(request.template_id, request.color_scheme_id),
            profile_id=profile_id,
        )

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        context = self.build_context(request)
        final_state = run_generate_state(
            request.input_path,
            request.target,
            request.output_path,
            target_slide_count=request.slides,
            settings=context.settings,
            style_profile=context.style_profile,
        )
        output = final_state.get("output_path")
        return AgentRunResult(
            output_path=Path(output) if output else None,
            warnings=list(final_state.get("warnings") or []),
            errors=list(final_state.get("errors") or []),
            compliance_report=final_state.get("compliance_report"),
            debug=dict(final_state.get("debug") or {}),
            workflow_state=dict(final_state),
        )

    def run_task(self, task_id: str, request: AgentRunRequest) -> AgentRunResult | None:
        try:
            self._write_task(task_id, "processing", 10, "读取配置")
            context = self.build_context(request)
            self._write_task(task_id, "processing", 25, "应用模板和配色")
            self._write_task(task_id, "processing", 50, "生成文档内容")
            final_state = run_generate_state(
                request.input_path,
                request.target,
                request.output_path,
                target_slide_count=request.slides,
                settings=context.settings,
                style_profile=context.style_profile,
            )
            result = final_state["output_path"] or str(request.output_path)
            self._write_task(
                task_id,
                "completed",
                100,
                "生成完成",
                result=str(result),
                compliance_report=final_state.get("compliance_report"),
            )
            return AgentRunResult(
                output_path=Path(result),
                warnings=list(final_state.get("warnings") or []),
                errors=list(final_state.get("errors") or []),
                compliance_report=final_state.get("compliance_report"),
                debug=dict(final_state.get("debug") or {}),
                workflow_state=dict(final_state),
            )
        except Exception as exc:
            self._write_task(
                task_id,
                "failed",
                0,
                "生成失败",
                error=str(exc),
                error_type=exc.__class__.__name__,
                friendly_error=friendly_error(exc),
            )
            return None

    def _runtime_settings(self, profile_id: str | None) -> Settings:
        settings = get_settings()
        user = self.user_manager.get_user(profile_id, include_secret=True) if profile_id else self.user_manager.get_current_user(include_secret=True)
        if user is None:
            return settings
        return replace(
            settings,
            llm_base_url=user.nga_endpoint,
            llm_api_key=user.auth_token,
            llm_model=user.llm_model,
            llm_provider=normalize_llm_provider(user.llm_provider),
            ppt_renderer=normalize_ppt_renderer(user.ppt_renderer),
        )

    def _style_profile(self, template_id: str | None, color_scheme_id: str | None) -> dict[str, Any]:
        style = load_style_profile()
        if template_id:
            overrides = self.template_manager.style_overrides(template_id)
            if overrides.get("fonts"):
                style.setdefault("fonts", {}).update(overrides["fonts"])
            if overrides.get("colors"):
                style.setdefault("colors", {}).update(overrides["colors"])
            if overrides.get("slide_size"):
                style["slide_size"] = overrides["slide_size"]
        if color_scheme_id:
            style = self.color_manager.apply_scheme_to_style(color_scheme_id, style)
        return style

    def _write_task(
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
    ) -> None:
        self.task_history.update_task(
            task_id,
            status,
            progress,
            current_step,
            result,
            error,
            error_type,
            friendly_error,
            compliance_report,
        )


def friendly_error(exc: Exception) -> str:
    message = str(exc)
    lower = message.lower()
    if "not found" in lower:
        return "生成依赖的文件或配置不存在，请重新选择文件、模板或配色后再试。"
    if "invalid" in lower or "validation" in lower:
        return "输入内容或模板格式无法识别，请换一个文件或检查配置。"
    if "ngaclient" in lower or "internal-network adapter" in lower:
        return "NGA 真实适配器尚未接入。外网阶段请使用 stub 模型配置，进入内网后再接 NGA。"
    if "huaweiskillrenderer" in lower or "hw_skill" in lower:
        return "华为渲染 Skill 尚未接入。外网阶段请使用 stub 渲染器，进入内网后再接 html2pptx 或 generate.py。"
    if "compliance" in lower:
        return "PPT 合规检查未通过，请查看合规报告并调整模板、字号、颜色或页脚。"
    if "local relay" in lower or "openai" in lower or "connection" in lower or "timeout" in lower:
        return "模型服务连接失败，请检查模型配置档案的 Endpoint、Token 和网络。"
    return "生成失败，请检查输入文件和当前配置后再试。"
