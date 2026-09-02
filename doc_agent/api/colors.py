from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from doc_agent.api.deps import get_color_manager
from doc_agent.colors.manager import ColorManager
from doc_agent.colors.models import ColorScheme


router = APIRouter(prefix="/api/colors", tags=["颜色管理"])


class ColorSchemeResponse(BaseModel):
    scheme_id: str
    name: str
    category: str
    description: str | None
    primary_color: str
    secondary_color: str
    accent_color: str
    background_color: str
    text_color: str
    is_system: bool


@router.get("/recommend")
async def recommend_colors(scenario: str, manager: ColorManager = Depends(get_color_manager)) -> dict:
    return {"recommendations": [item.model_dump(mode="json") for item in manager.recommend_color_scheme(scenario)]}


@router.get("/list")
async def list_colors(category: str | None = None, manager: ColorManager = Depends(get_color_manager)) -> dict:
    return {
        "schemes": [
            ColorSchemeResponse(
                scheme_id=scheme.scheme_id,
                name=scheme.name,
                category=scheme.category,
                description=scheme.description,
                primary_color=scheme.primary_color,
                secondary_color=scheme.secondary_color,
                accent_color=scheme.accent_color,
                background_color=scheme.background_color,
                text_color=scheme.text_color,
                is_system=scheme.is_system,
            ).model_dump(mode="json")
            for scheme in manager.list_schemes(category)
        ]
    }


@router.get("/{scheme_id}")
async def get_color_scheme(scheme_id: str, manager: ColorManager = Depends(get_color_manager)) -> dict:
    scheme = manager.get_scheme(scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail="Color scheme not found")
    return scheme.model_dump(mode="json")


@router.post("/create")
async def create_custom_scheme(scheme_data: ColorScheme, manager: ColorManager = Depends(get_color_manager)) -> dict:
    try:
        scheme = manager.create_custom_scheme(scheme_data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "scheme_id": scheme.scheme_id, "message": "颜色方案创建成功"}
