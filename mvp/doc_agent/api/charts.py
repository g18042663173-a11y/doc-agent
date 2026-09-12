from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from doc_agent.api.deps import get_chart_manager
from doc_agent.charts.manager import ChartManager
from doc_agent.charts.models import ChartConfig


router = APIRouter(prefix="/api/charts", tags=["图表系统"])


class ChartRecommendRequest(BaseModel):
    data_description: str
    data_characteristics: dict[str, Any] = Field(default_factory=dict)


@router.post("/recommend")
async def recommend_chart(request: ChartRecommendRequest, manager: ChartManager = Depends(get_chart_manager)) -> dict:
    recommendation = manager.recommend_chart_type(request.data_description, request.data_characteristics)
    return {"recommendation": recommendation.model_dump(mode="json")}


@router.post("/generate")
async def generate_chart(request: ChartConfig, manager: ChartManager = Depends(get_chart_manager)) -> dict:
    return {"chart": manager.generate_chart(request)}
