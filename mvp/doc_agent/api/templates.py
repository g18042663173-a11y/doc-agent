from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from doc_agent.api.deps import get_template_manager
from doc_agent.config import get_settings
from doc_agent.templates.manager import TemplateManager


router = APIRouter(prefix="/api/templates", tags=["模板管理"])


class TemplateResponse(BaseModel):
    template_id: str
    name: str
    category: str
    description: str
    thumbnail: str | None
    preview: str | None
    is_system: bool
    style_summary: dict | None = None


@router.get("/list")
async def list_templates(category: str | None = None, manager: TemplateManager = Depends(get_template_manager)) -> dict:
    templates = manager.list_templates(category)
    return {
        "templates": [
            TemplateResponse(
                template_id=template.template_id,
                name=template.name,
                category=template.category.value,
                description=template.description,
                thumbnail=template.thumbnail,
                preview=template.preview,
                is_system=template.is_system,
                style_summary=(template.custom_settings or {}).get("analysis"),
            ).model_dump(mode="json")
            for template in templates
        ]
    }


@router.get("/{template_id}")
async def get_template(template_id: str, manager: TemplateManager = Depends(get_template_manager)) -> dict:
    template = manager.get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template.model_dump(mode="json")


@router.post("/import")
async def import_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    category: str = Form("business"),
    manager: TemplateManager = Depends(get_template_manager),
) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".pptx":
        raise HTTPException(status_code=400, detail="模板只支持 .pptx 文件，请重新选择 PowerPoint 模板。")
    temp_dir = get_settings().data_dir / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"template-{Path(file.filename or 'template.pptx').name}"
    temp_path.write_bytes(await file.read())
    try:
        template = manager.import_template(temp_path, name, category)
    except Exception as exc:
        message = str(exc)
        if "Invalid PPTX template" in message:
            detail = "模板文件无法解析，请确认它是有效的 .pptx 文件。"
        elif "is not a valid TemplateCategory" in message:
            detail = "模板分类无效，请选择 business、tech、education 或 creative。"
        else:
            detail = "模板导入失败，请换一个 PPTX 文件或检查文件是否损坏。"
        raise HTTPException(status_code=400, detail=detail) from exc
    finally:
        temp_path.unlink(missing_ok=True)
    return {
        "success": True,
        "template_id": template.template_id,
        "message": "模板导入成功",
        "style_summary": (template.custom_settings or {}).get("analysis"),
    }
