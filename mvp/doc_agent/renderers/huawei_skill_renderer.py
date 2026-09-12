from __future__ import annotations

from pathlib import Path
from typing import Any

from doc_agent.config import get_settings
from doc_agent.ir.schemas import DeckIR
from doc_agent.renderers.base import BaseRenderer


class HuaweiSkillRenderer(BaseRenderer):
    """Internal-network adapter placeholder for Huawei PPT rendering Skill."""

    def __init__(self, skill_entrypoint: str | None = None) -> None:
        self.skill_entrypoint = skill_entrypoint or "html2pptx"
        self.settings = get_settings()

    def render(self, ir: dict[str, Any], output_path: str | Path) -> Path:
        DeckIR.model_validate(ir)
        raise RuntimeError(
            "HuaweiSkillRenderer is an internal-network adapter placeholder. "
            "Use PPT_RENDERER=stub outside the intranet. Inside the intranet, call the official "
            "html2pptx Skill path by default and keep generate.py as a fallback if the Skill exposes it."
        )
