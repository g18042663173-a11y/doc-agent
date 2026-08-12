from __future__ import annotations

from pathlib import Path
import shutil
import xml.etree.ElementTree as ElementTree

import pytest

from app.diagram.mermaid_diagram import (
    DirectionRules,
    MermaidDiagramError,
    MermaidDiagramUnavailable,
    decide_flowchart_direction,
    parse_mermaid_flowchart,
    render_mermaid_diagram,
    render_mermaid_svg,
)


DOT_AVAILABLE = shutil.which("dot") is not None


def test_parse_flowchart_allows_arrow_tokens_inside_node_labels() -> None:
    flowchart = parse_mermaid_flowchart(
        "flowchart LR\n"
        "A[输入 --> 处理]\n"
        "B[结果]\n"
        "A --> B\n"
    )

    node_a = next(node for node in flowchart.nodes if node.identifier == "A")
    assert node_a.label == "输入 --> 处理"
    assert [edge.kind for edge in flowchart.edges] == ["arrow"]


def test_parse_flowchart_keeps_nodes_edges_labels_and_direction() -> None:
    flowchart = parse_mermaid_flowchart(
        """flowchart LR
        input[输入文档] --> parser[结构解析]
        parser -->|DocumentIR| output((Markdown))
        """
    )

    assert flowchart.rankdir == "LR"
    assert [(node.identifier, node.label, node.shape) for node in flowchart.nodes] == [
        ("input", "输入文档", "box"),
        ("parser", "结构解析", "box"),
        ("output", "Markdown", "ellipse"),
    ]
    assert [(edge.source, edge.target, edge.label) for edge in flowchart.edges] == [
        ("input", "parser", None),
        ("parser", "output", "DocumentIR"),
    ]


def test_auto_direction_uses_left_to_right_for_a_small_linear_chain() -> None:
    flowchart = parse_mermaid_flowchart(
        """flowchart TD
        input[输入] --> parse[解析] --> validate[校验] --> output[输出]
        """
    )

    decision = decide_flowchart_direction(flowchart)

    assert decision.direction == "LR"
    assert decision.reason == "linear_chain"
    assert decision.node_count == 4


def test_auto_direction_uses_top_to_bottom_for_a_branch_or_merge() -> None:
    flowchart = parse_mermaid_flowchart(
        """flowchart LR
        input[输入] --> gate{校验}
        gate --> publish[发布]
        gate --> repair[修复]
        """
    )

    decision = decide_flowchart_direction(flowchart)

    assert decision.direction == "TD"
    assert decision.reason == "branch_or_merge"


def test_auto_direction_uses_top_to_bottom_when_node_count_exceeds_threshold() -> None:
    flowchart = parse_mermaid_flowchart(
        "flowchart LR\n" + " --> ".join(f"N{index}" for index in range(1, 10))
    )

    decision = decide_flowchart_direction(flowchart)

    assert decision.direction == "TD"
    assert decision.reason == "node_count"
    assert decision.node_count == 9


def test_auto_direction_uses_top_to_bottom_for_a_large_architecture_graph() -> None:
    flowchart = parse_mermaid_flowchart(
        """flowchart LR
        source[输入文件] --> parser[解析器] --> document_ir[DocumentIR]
        document_ir --> prompting[Prompt 组装] --> generator[Generator] --> deck_ir[DeckIR]
        deck_ir --> validation[IR 校验]
        validation --> word[Word 输出]
        validation --> deck[PPT 输出]
        """
    )

    decision = decide_flowchart_direction(flowchart)

    assert decision.direction == "TD"
    assert decision.reason == "node_count"
    assert decision.node_count == 9


def test_auto_direction_accepts_configurable_linear_chain_threshold() -> None:
    flowchart = parse_mermaid_flowchart(
        "flowchart TD\n" + " --> ".join(f"N{index}" for index in range(1, 8))
    )

    default_decision = decide_flowchart_direction(flowchart)
    configured_decision = decide_flowchart_direction(
        flowchart,
        DirectionRules(max_linear_nodes_lr=7),
    )

    assert default_decision.direction == "TD"
    assert default_decision.reason == "fallback"
    assert configured_decision.direction == "LR"
    assert configured_decision.reason == "linear_chain"


def test_auto_direction_accepts_configurable_node_count_threshold() -> None:
    flowchart = parse_mermaid_flowchart(
        "flowchart LR\n" + " --> ".join(f"N{index}" for index in range(1, 5))
    )

    decision = decide_flowchart_direction(
        flowchart,
        DirectionRules(td_node_threshold=4),
    )

    assert decision.direction == "TD"
    assert decision.reason == "node_count"


@pytest.mark.skipif(not DOT_AVAILABLE, reason="Graphviz dot is not installed")
def test_render_mermaid_svg_uses_layered_left_to_right_layout() -> None:
    svg = render_mermaid_svg(
        """flowchart LR
        source[输入] --> transform[转换]
        transform --> target[输出]
        """
    )

    positions = _node_centers(svg)
    assert svg.startswith("<?xml")
    assert all(label in svg for label in ("输入", "转换", "输出"))
    assert positions["source"][0] < positions["transform"][0] < positions["target"][0]
    assert _edge_titles(svg) == {"source->transform", "transform->target"}


@pytest.mark.skipif(not DOT_AVAILABLE, reason="Graphviz dot is not installed")
def test_auto_mode_overrides_declared_td_for_a_small_linear_chain() -> None:
    svg = render_mermaid_svg(
        """flowchart TD
        input[输入] --> parse[解析] --> validate[校验] --> output[输出]
        """,
        direction_mode="auto",
    )

    centers = _node_centers(svg)

    assert centers["input"][0] < centers["parse"][0] < centers["validate"][0] < centers["output"][0]


@pytest.mark.skipif(not DOT_AVAILABLE, reason="Graphviz dot is not installed")
def test_auto_mode_overrides_declared_lr_for_a_branching_flowchart() -> None:
    svg = render_mermaid_svg(
        """flowchart LR
        input[输入] --> gate{校验}
        gate -->|通过| publish[发布]
        gate -->|失败| repair[修复]
        """,
        direction_mode="auto",
    )

    centers = _node_centers(svg)

    assert centers["input"][1] < centers["gate"][1]
    assert centers["gate"][1] < centers["publish"][1]
    assert centers["gate"][1] < centers["repair"][1]


@pytest.mark.skipif(not DOT_AVAILABLE, reason="Graphviz dot is not installed")
def test_auto_mode_uses_top_to_bottom_for_a_large_architecture_graph() -> None:
    svg = render_mermaid_svg(
        """flowchart LR
        source[输入文件] --> parser[解析器] --> document_ir[DocumentIR]
        document_ir --> prompting[Prompt 组装] --> generator[Generator] --> deck_ir[DeckIR]
        deck_ir --> validation[IR 校验]
        validation --> word[Word 输出]
        validation --> deck[PPT 输出]
        """,
        direction_mode="auto",
    )

    centers = _node_centers(svg)

    assert centers["source"][1] < centers["parser"][1] < centers["document_ir"][1]
    assert centers["validation"][1] < centers["word"][1]
    assert centers["validation"][1] < centers["deck"][1]


@pytest.mark.skipif(not DOT_AVAILABLE, reason="Graphviz dot is not installed")
def test_preserve_mode_keeps_declared_right_to_left_direction() -> None:
    svg = render_mermaid_svg(
        """flowchart RL
        input[输入] --> parse[解析] --> output[输出]
        """,
        direction_mode="preserve",
    )

    centers = _node_centers(svg)

    assert centers["input"][0] > centers["parse"][0] > centers["output"][0]


@pytest.mark.skipif(not DOT_AVAILABLE, reason="Graphviz dot is not installed")
def test_render_branching_flowchart_connects_each_declared_edge() -> None:
    svg = render_mermaid_svg(
        """flowchart TD
        start((开始)) --> gate{是否通过}
        gate -->|是| publish[发布]
        gate -->|否| repair[修复]
        repair -.-> gate
        """
    )

    centers = _node_centers(svg)
    assert set(centers) == {"start", "gate", "publish", "repair"}
    assert centers["start"][1] < centers["gate"][1]
    assert _edge_titles(svg) == {
        "start->gate",
        "gate->publish",
        "gate->repair",
        "repair->gate",
    }
    assert all(label in svg for label in ("是否通过", "发布", "修复", "是", "否"))


@pytest.mark.skipif(not DOT_AVAILABLE, reason="Graphviz dot is not installed")
def test_render_mermaid_diagram_writes_svg_and_png(tmp_path: Path) -> None:
    source = "flowchart TD\nA[采集] --> B[清洗] --> C[分析] --> D[归档]"
    svg_path = render_mermaid_diagram(source, tmp_path / "pipeline.svg")
    png_path = render_mermaid_diagram(source, tmp_path / "pipeline.png")

    assert svg_path.read_text(encoding="utf-8").startswith("<?xml")
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize(
    "source, message",
    [
        ("sequenceDiagram\nA->>B: hello", "expected 'flowchart TD'"),
        ("flowchart TD\nsubgraph core\nA --> B\nend", "unsupported Mermaid instruction"),
        ("flowchart TD\nA -->", "edge is missing a node"),
        ("flowchart TD\nA[]", "labels must not be empty"),
    ],
)
def test_parser_rejects_unsupported_or_malformed_mermaid(source: str, message: str) -> None:
    with pytest.raises(MermaidDiagramError, match=message):
        parse_mermaid_flowchart(source)


def test_renderer_rejects_unknown_output_format(tmp_path: Path) -> None:
    with pytest.raises(MermaidDiagramError, match=".svg or .png"):
        render_mermaid_diagram("flowchart TD\nA --> B", tmp_path / "diagram.pdf")


def test_renderer_reports_missing_graphviz_python_package(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name == "graphviz":
            raise ImportError("missing graphviz")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    with pytest.raises(MermaidDiagramUnavailable, match="Python package 'graphviz' is not installed"):
        render_mermaid_svg("flowchart TD\nA --> B")


def _node_centers(svg: str) -> dict[str, tuple[float, float]]:
    root = ElementTree.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    centers: dict[str, tuple[float, float]] = {}
    for group in root.findall(".//svg:g[@class='node']", namespace):
        title = group.find("svg:title", namespace)
        text = group.find("svg:text", namespace)
        if title is None or text is None or not title.text:
            continue
        centers[title.text] = (float(text.attrib["x"]), float(text.attrib["y"]))
    return centers


def _edge_titles(svg: str) -> set[str]:
    root = ElementTree.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    return {
        title.text
        for group in root.findall(".//svg:g[@class='edge']", namespace)
        if (title := group.find("svg:title", namespace)) is not None and title.text
    }
