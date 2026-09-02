from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from doc_agent.colors.manager import ColorManager
from doc_agent.colors.models import ColorScheme
from doc_agent.config import get_settings
from doc_agent.templates.manager import TemplateManager
from doc_agent.templates.models import TemplateConfig
from doc_agent.users.manager import TOKEN_MASK, UserManager
from doc_agent.users.models import UserConfig
from doc_agent.utils.metrics import app_metrics


router = APIRouter(tags=["系统配置"])


class ImportConfigRequest(BaseModel):
    users: list[UserConfig] = Field(default_factory=list)
    templates: list[TemplateConfig] = Field(default_factory=list)
    color_schemes: list[ColorScheme] = Field(default_factory=list)


@router.get("/api/system/health")
async def system_health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": "0.1.0",
        "data_dir": str(settings.data_dir),
        "output_dir": str(settings.output_dir),
        "llm_provider": settings.llm_provider,
        "ppt_renderer": settings.ppt_renderer,
        "ppt_compliance_gate": settings.ppt_compliance_gate,
        "preview_export_available": _tool_available(settings.soffice_path, "soffice")
        and _tool_available(settings.pdftoppm_path, "pdftoppm"),
    }


@router.get("/api/system/metrics")
async def system_metrics() -> dict[str, Any]:
    settings = get_settings()
    return {
        "app": app_metrics.snapshot(),
        "tasks": _task_counts(settings.data_dir / "tasks"),
        "storage": _storage_snapshot(settings.data_dir, settings.output_dir),
    }


@router.get("/api/config/export")
async def export_config() -> dict[str, Any]:
    settings = get_settings()
    users = UserManager().list_users()
    templates = TemplateManager().list_templates()
    color_schemes = ColorManager().list_schemes()
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "settings": _settings_snapshot(),
        "users": [user.model_dump(mode="json") for user in users],
        "templates": [template.model_dump(mode="json") for template in templates],
        "color_schemes": [scheme.model_dump(mode="json") for scheme in color_schemes],
        "paths": {
            "data_dir": str(settings.data_dir),
            "output_dir": str(settings.output_dir),
        },
    }


@router.post("/api/config/import")
async def import_config(request: ImportConfigRequest) -> dict[str, Any]:
    user_manager = UserManager()
    template_manager = TemplateManager()
    color_manager = ColorManager()
    imported_users = 0
    skipped_users = 0
    imported_templates = 0
    skipped_templates = 0
    imported_colors = 0

    for user in request.users:
        if not user.auth_token or user.auth_token == TOKEN_MASK:
            skipped_users += 1
            continue
        try:
            user_manager.create_user(user)
            imported_users += 1
        except ValueError:
            user_manager.update_user(user.user_id, user.model_dump(mode="json"))
            imported_users += 1

    for template in request.templates:
        if template.is_system:
            skipped_templates += 1
            continue
        try:
            template_manager.upsert_template(template)
            imported_templates += 1
        except Exception:
            skipped_templates += 1

    for scheme in request.color_schemes:
        color_manager.create_custom_scheme(scheme)
        imported_colors += 1

    return {
        "success": True,
        "imported_users": imported_users,
        "skipped_users": skipped_users,
        "imported_templates": imported_templates,
        "skipped_templates": skipped_templates,
        "imported_color_schemes": imported_colors,
    }


def _settings_snapshot() -> dict[str, Any]:
    settings = get_settings()
    return {
        "llm_provider": settings.llm_provider,
        "llm_base_url": settings.llm_base_url,
        "llm_api_key": TOKEN_MASK if settings.llm_api_key else "",
        "llm_model": settings.llm_model,
        "ppt_renderer": settings.ppt_renderer,
        "ppt_compliance_gate": settings.ppt_compliance_gate,
        "use_langgraph": settings.use_langgraph,
        "default_target_slides": settings.default_target_slides,
        "max_input_chars": settings.max_input_chars,
        "max_repair_attempts": settings.max_repair_attempts,
        "save_debug_artifacts": settings.save_debug_artifacts,
        "log_level": settings.log_level,
    }


def _tool_available(configured: str | None, binary: str) -> bool:
    if configured:
        path = Path(configured)
        return path.exists() or shutil.which(configured) is not None
    return shutil.which(binary) is not None


def _task_counts(tasks_dir: Path) -> dict[str, int]:
    counts = {"total": 0, "queued": 0, "processing": 0, "completed": 0, "failed": 0, "not_found": 0}
    if not tasks_dir.exists():
        return counts
    for task_file in tasks_dir.glob("*.json"):
        try:
            data = json.loads(task_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        status = str(data.get("status", "unknown"))
        counts["total"] += 1
        counts[status] = counts.get(status, 0) + 1
    return counts


def _storage_snapshot(data_dir: Path, output_dir: Path) -> dict[str, Any]:
    return {
        "data_dir_exists": data_dir.exists(),
        "output_dir_exists": output_dir.exists(),
        "data_bytes": _directory_size(data_dir),
        "output_bytes": _directory_size(output_dir),
    }


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total
