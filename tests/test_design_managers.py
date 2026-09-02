from pathlib import Path

import pytest
from pptx import Presentation

from doc_agent.charts import ChartConfig, ChartData, ChartManager, ChartType
from doc_agent.colors import ColorManager, ColorScheme
from doc_agent.smartart import SmartArtConfig, SmartArtManager, SmartArtNode, SmartArtType
from doc_agent.templates import TemplateManager


def test_color_manager_lists_recommends_and_validates_schemes(tmp_path: Path) -> None:
    manager = ColorManager(tmp_path / "colors")

    assert manager.get_scheme("business_blue") is not None
    assert manager.recommend_color_scheme("商务报告")[0].scheme_id == "business_blue"

    custom = manager.create_custom_scheme(
        ColorScheme(
            name="自定义",
            category="business",
            primary_color="#123456",
            secondary_color="#234567",
            accent_color="#345678",
            background_color="#FFFFFF",
            text_color="#111111",
        )
    )
    assert manager.get_scheme(custom.scheme_id) is not None

    with pytest.raises(ValueError):
        manager.create_custom_scheme(
            ColorScheme(
                name="错误",
                category="business",
                primary_color="123456",
                secondary_color="#234567",
                accent_color="#345678",
                background_color="#FFFFFF",
                text_color="#111111",
            )
        )


def test_template_manager_lists_applies_and_imports_templates(tmp_path: Path) -> None:
    manager = TemplateManager(tmp_path / "templates")
    assert manager.get_template("business_report") is not None

    enhanced = manager.apply_template({"deck_title": "Demo", "slides": []}, "business_report")
    assert enhanced["template_id"] == "business_report"

    source = tmp_path / "input_template.pptx"
    Presentation().save(str(source))
    imported = manager.import_template(source, "导入模板", "business")

    assert imported.name == "导入模板"
    assert Path(imported.file_path).exists()
    assert imported.custom_settings["analysis"]["mode"] == "style_apply"
    assert imported.custom_settings["analysis"]["slide_size"]["width_inches"] > 0
    assert manager.style_overrides(imported.template_id)["slide_size"]["height_inches"] > 0
    assert manager.get_template(imported.template_id) is not None

    restored = imported.model_copy(update={"file_path": f"/old-computer/data/templates/custom/{Path(imported.file_path).name}"})
    manager.upsert_template(restored)
    assert manager.get_template(imported.template_id).file_path == imported.file_path


def test_chart_manager_recommends_and_generates_chart_ir() -> None:
    manager = ChartManager()
    recommendation = manager.recommend_chart_type(
        "monthly trend by time",
        {"data_type": "time_series", "purpose": "trend"},
    )
    assert recommendation.chart_type == ChartType.LINE

    chart = manager.generate_chart(
        ChartConfig(
            chart_type=ChartType.BAR,
            title="模块状态",
            data=ChartData(labels=["Parser"], datasets=[{"name": "完成度", "data": [1]}]),
        )
    )
    assert chart["chart_type"] == "bar"
    assert chart["data"]["labels"] == ["Parser"]


def test_smartart_manager_generates_expected_layouts() -> None:
    manager = SmartArtManager()
    nodes = [SmartArtNode(id="n1", text="开始")]

    process = manager.generate_smartart(nodes, SmartArtConfig(smartart_type=SmartArtType.PROCESS))
    cycle = manager.generate_smartart(nodes, SmartArtConfig(smartart_type=SmartArtType.CYCLE))
    timeline = manager.generate_smartart(nodes, SmartArtConfig(smartart_type=SmartArtType.TIMELINE))

    assert process["layout"] == "horizontal"
    assert cycle["layout"] == "circular"
    assert timeline["layout"] == "timeline"
