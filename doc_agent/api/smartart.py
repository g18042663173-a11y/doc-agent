from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from doc_agent.api.deps import get_smartart_manager
from doc_agent.smartart.manager import SmartArtManager
from doc_agent.smartart.models import SmartArtConfig, SmartArtNode


router = APIRouter(prefix="/api/smartart", tags=["SmartArt系统"])


class SmartArtGenerateRequest(BaseModel):
    nodes: list[SmartArtNode]
    config: SmartArtConfig


@router.get("/types")
async def smartart_types(manager: SmartArtManager = Depends(get_smartart_manager)) -> dict:
    return {"types": manager.supported_types()}


@router.post("/generate")
async def generate_smartart(request: SmartArtGenerateRequest, manager: SmartArtManager = Depends(get_smartart_manager)) -> dict:
    return {"smartart": manager.generate_smartart(request.nodes, request.config)}
