from __future__ import annotations

from doc_agent.smartart.models import SmartArtConfig, SmartArtNode, SmartArtType


class SmartArtManager:
    def generate_smartart(self, nodes: list[SmartArtNode], config: SmartArtConfig) -> dict:
        if config.smartart_type == SmartArtType.PROCESS:
            return self._generate(nodes, config, "horizontal")
        if config.smartart_type in {SmartArtType.HIERARCHY, SmartArtType.ORG_CHART}:
            return self._generate(nodes, config, "tree")
        if config.smartart_type == SmartArtType.CYCLE:
            return self._generate(nodes, config, "circular")
        if config.smartart_type == SmartArtType.TIMELINE:
            return self._generate(nodes, config, "timeline")
        if config.smartart_type == SmartArtType.MATRIX:
            return self._generate(nodes, config, "grid")
        if config.smartart_type == SmartArtType.PYRAMID:
            return self._generate(nodes, config, "pyramid")
        if config.smartart_type == SmartArtType.RELATIONSHIP:
            return self._generate(nodes, config, "radial")
        raise ValueError(f"Unsupported SmartArt type: {config.smartart_type}")

    @staticmethod
    def supported_types() -> list[str]:
        return [item.value for item in SmartArtType]

    @staticmethod
    def _generate(nodes: list[SmartArtNode], config: SmartArtConfig, layout: str) -> dict:
        return {
            "type": config.smartart_type.value,
            "nodes": [node.model_dump(mode="json") for node in nodes],
            "config": config.model_dump(mode="json"),
            "layout": layout,
        }
