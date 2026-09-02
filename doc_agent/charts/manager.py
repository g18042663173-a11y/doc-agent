from __future__ import annotations

from typing import Any

from doc_agent.charts.models import ChartConfig, ChartRecommendation, ChartType


class ChartManager:
    def __init__(self) -> None:
        self.recommendation_rules = self._initialize_recommendation_rules()

    def recommend_chart_type(self, data_description: str, data_characteristics: dict[str, Any]) -> ChartRecommendation:
        analysis = self._analyze_data(data_description, data_characteristics)
        recommendations: list[ChartRecommendation] = []
        for rule in self.recommendation_rules:
            score = self._calculate_rule_score(analysis, rule)
            if score > 0:
                recommendations.append(
                    ChartRecommendation(
                        chart_type=rule["chart_type"],
                        confidence=score,
                        reason=rule["reason"],
                        data_requirements=rule["data_requirements"],
                        styling_tips=rule["styling_tips"],
                    )
                )
        if not recommendations:
            return self._get_default_recommendation()
        return max(recommendations, key=lambda item: item.confidence)

    def generate_chart(self, chart_config: ChartConfig) -> dict[str, Any]:
        return {
            "chart_type": chart_config.chart_type.value,
            "title": chart_config.title,
            "data": chart_config.data.model_dump(mode="json"),
            "style": chart_config.style_config,
            "layout": chart_config.layout_config,
        }

    def _initialize_recommendation_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "chart_type": ChartType.BAR,
                "conditions": {"data_type": ["categorical", "discrete"], "purpose": ["comparison", "ranking"]},
                "reason": "柱状图适合比较不同类别的数值大小",
                "data_requirements": ["分类数据", "数值型数据"],
                "styling_tips": ["使用对比色区分类别", "添加数据标签"],
            },
            {
                "chart_type": ChartType.LINE,
                "conditions": {"data_type": ["time_series"], "purpose": ["trend", "forecast"]},
                "reason": "折线图适合展示时间序列趋势",
                "data_requirements": ["时间维度", "连续数值"],
                "styling_tips": ["突出关键拐点", "避免过多系列"],
            },
            {
                "chart_type": ChartType.PIE,
                "conditions": {"data_type": ["proportion", "categorical"], "purpose": ["composition", "share"]},
                "reason": "饼图适合展示少量类别的占比结构",
                "data_requirements": ["类别数据", "占比或总量"],
                "styling_tips": ["类别不超过6个", "显示百分比"],
            },
            {
                "chart_type": ChartType.SCATTER,
                "conditions": {"data_type": ["numeric"], "purpose": ["correlation", "distribution"]},
                "reason": "散点图适合观察两个数值变量的关系",
                "data_requirements": ["两个数值维度"],
                "styling_tips": ["标注异常点", "必要时添加趋势线"],
            },
        ]

    @staticmethod
    def _analyze_data(description: str, characteristics: dict[str, Any]) -> dict[str, Any]:
        return {
            "description": description.lower(),
            "data_type": characteristics.get("data_type", "unknown"),
            "purpose": characteristics.get("purpose", "unknown"),
            "data_size": characteristics.get("data_size", "medium"),
        }

    @staticmethod
    def _calculate_rule_score(analysis: dict[str, Any], rule: dict[str, Any]) -> float:
        score = 0.0
        conditions = rule["conditions"]
        description = analysis["description"]
        if analysis["data_type"] in conditions.get("data_type", []):
            score += 0.45
        elif any(item in description for item in conditions.get("data_type", [])):
            score += 0.2
        if analysis["purpose"] in conditions.get("purpose", []):
            score += 0.45
        elif any(item in description for item in conditions.get("purpose", [])):
            score += 0.25
        return min(score, 1.0)

    @staticmethod
    def _get_default_recommendation() -> ChartRecommendation:
        return ChartRecommendation(
            chart_type=ChartType.BAR,
            confidence=0.5,
            reason="柱状图是通用且易读的默认图表类型",
            data_requirements=["分类数据", "数值型数据"],
            styling_tips=["使用清晰标签", "添加数据值"],
        )
