"""Render a controlled Mermaid flowchart subset with the offline Graphviz runtime.

This module deliberately accepts only the Mermaid constructs useful for
architecture diagrams: ``flowchart``/``graph`` headers, node declarations,
directed or undirected edges, optional edge labels, and TD/LR directions.
Unsupported Mermaid diagrams are rejected rather than silently rendered with
lost semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
from typing import Literal


DiagramFormat = Literal["svg", "png"]
DirectionMode = Literal["preserve", "auto"]
AutoDirection = Literal["LR", "TD"]
DirectionReason = Literal["linear_chain", "branch_or_merge", "node_count", "fallback"]

_HEADER_RE = re.compile(r"^(?:flowchart|graph)\s+(?P<direction>TB|TD|BT|LR|RL)$", re.IGNORECASE)
_NODE_RE = re.compile(
    r"^(?P<id>[A-Za-z_][A-Za-z0-9_-]*)(?:"
    r"\(\((?P<ellipse>[^()]*)\)\)"
    r"|\[(?P<box>[^\[\]]*)\]"
    r"|\((?P<rounded>[^()]*)\)"
    r"|\{(?P<diamond>[^{}]*)\}"
    r")?$"
)
_EDGE_RE = re.compile(
    r"(?P<arrow>-.->|==>|-->|---)(?:\s*\|\s*(?P<label>[^|]+?)\s*\|)?"
)
_UNSUPPORTED_PREFIXES = (
    "subgraph",
    "end",
    "classdef",
    "class ",
    "style ",
    "linkstyle",
    "click ",
    "direction ",
)
_RANK_DIRECTIONS = {"TD": "TB", "TB": "TB", "BT": "BT", "LR": "LR", "RL": "RL"}
_SHAPE_ATTRIBUTES = {
    "box": {"shape": "box", "style": "rounded,filled", "fillcolor": "#FFFFFF"},
    "rounded": {"shape": "box", "style": "rounded,filled", "fillcolor": "#F5F5F5"},
    "ellipse": {"shape": "ellipse", "style": "filled", "fillcolor": "#FFFFFF"},
    "diamond": {"shape": "diamond", "style": "filled", "fillcolor": "#FFF5F5"},
}


class MermaidDiagramError(ValueError):
    """Raised when Mermaid text is outside the supported flowchart subset."""


class MermaidDiagramUnavailable(RuntimeError):
    """Raised when the offline Graphviz Python package or ``dot`` runtime is missing."""


@dataclass(frozen=True)
class MermaidNode:
    identifier: str
    label: str
    shape: Literal["box", "rounded", "ellipse", "diamond"]


@dataclass(frozen=True)
class MermaidEdge:
    source: str
    target: str
    kind: Literal["arrow", "line", "dotted", "thick"]
    label: str | None = None


@dataclass(frozen=True)
class MermaidFlowchart:
    rankdir: Literal["TB", "BT", "LR", "RL"]
    nodes: tuple[MermaidNode, ...]
    edges: tuple[MermaidEdge, ...]


@dataclass(frozen=True)
class DirectionRules:
    """Thresholds used when ``direction_mode="auto"`` is requested."""

    max_linear_nodes_lr: int = 6
    td_node_threshold: int = 9
    fallback_direction: AutoDirection = "TD"

    def __post_init__(self) -> None:
        if self.max_linear_nodes_lr < 1:
            raise ValueError("max_linear_nodes_lr must be at least 1")
        if self.td_node_threshold < 1:
            raise ValueError("td_node_threshold must be at least 1")
        if self.fallback_direction not in {"LR", "TD"}:
            raise ValueError("fallback_direction must be 'LR' or 'TD'")


@dataclass(frozen=True)
class DirectionDecision:
    """The canonical direction and rule that selected it."""

    direction: AutoDirection
    reason: DirectionReason
    node_count: int


def render_mermaid_diagram(
    mermaid_text: str,
    output_path: Path,
    *,
    direction_mode: DirectionMode = "preserve",
    direction_rules: DirectionRules | None = None,
) -> Path:
    """Render supported Mermaid flowchart text into a ``.svg`` or ``.png`` file."""

    output_format = _output_format(output_path)
    flowchart = _apply_direction_mode(
        parse_mermaid_flowchart(mermaid_text),
        direction_mode=direction_mode,
        direction_rules=direction_rules,
    )
    payload = _render_payload(flowchart, output_format)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "svg":
        output_path.write_text(payload, encoding="utf-8")
    else:
        output_path.write_bytes(payload)
    return output_path


def render_mermaid_svg(
    mermaid_text: str,
    *,
    direction_mode: DirectionMode = "preserve",
    direction_rules: DirectionRules | None = None,
) -> str:
    """Render supported Mermaid flowchart text and return the SVG payload."""

    flowchart = _apply_direction_mode(
        parse_mermaid_flowchart(mermaid_text),
        direction_mode=direction_mode,
        direction_rules=direction_rules,
    )
    payload = _render_payload(flowchart, "svg")
    assert isinstance(payload, str)
    return payload


def parse_mermaid_flowchart(mermaid_text: str) -> MermaidFlowchart:
    """Parse the small, explicit Mermaid flowchart subset used by this generator."""

    lines = _source_lines(mermaid_text)
    if not lines:
        raise MermaidDiagramError("Mermaid diagram is empty")
    header_line, header_text = lines[0]
    header = _HEADER_RE.fullmatch(header_text)
    if header is None:
        raise MermaidDiagramError(
            f"line {header_line}: expected 'flowchart TD' or 'flowchart LR' header"
        )

    nodes: dict[str, MermaidNode] = {}
    edges: list[MermaidEdge] = []
    for line_number, text in lines[1:]:
        if text.lower().startswith(_UNSUPPORTED_PREFIXES):
            raise MermaidDiagramError(f"line {line_number}: unsupported Mermaid instruction: {text}")
        # Prefer a whole-line node match: node labels may legally contain arrow
        # tokens (A[输入 --> 处理]), which must not reroute the line to edge
        # parsing.
        if _NODE_RE.fullmatch(text):
            _upsert_node(nodes, _parse_node(text, line_number))
        else:
            _parse_edge_line(text, line_number, nodes, edges)

    if not nodes:
        raise MermaidDiagramError("Mermaid flowchart has no nodes")
    return MermaidFlowchart(
        rankdir=_RANK_DIRECTIONS[header.group("direction").upper()],
        nodes=tuple(nodes.values()),
        edges=tuple(edges),
    )


def decide_flowchart_direction(
    flowchart: MermaidFlowchart,
    rules: DirectionRules | None = None,
) -> DirectionDecision:
    """Choose a canonical LR or TD direction from the graph's topology.

    The decision intentionally ignores Mermaid's declared direction.  Callers
    opt in through ``direction_mode="auto"``; the default rendering path keeps
    the source declaration unchanged.
    """

    effective_rules = rules or DirectionRules()
    node_count = len(flowchart.nodes)
    incoming, outgoing = _node_degrees(flowchart)

    if node_count >= effective_rules.td_node_threshold:
        return DirectionDecision(direction="TD", reason="node_count", node_count=node_count)
    if any(degree > 1 for degree in incoming.values()) or any(
        degree > 1 for degree in outgoing.values()
    ):
        return DirectionDecision(direction="TD", reason="branch_or_merge", node_count=node_count)
    if (
        node_count <= effective_rules.max_linear_nodes_lr
        and _is_single_linear_chain(flowchart, incoming, outgoing)
    ):
        return DirectionDecision(direction="LR", reason="linear_chain", node_count=node_count)
    return DirectionDecision(
        direction=effective_rules.fallback_direction,
        reason="fallback",
        node_count=node_count,
    )


def _apply_direction_mode(
    flowchart: MermaidFlowchart,
    *,
    direction_mode: DirectionMode,
    direction_rules: DirectionRules | None,
) -> MermaidFlowchart:
    if direction_mode == "preserve":
        return flowchart
    if direction_mode != "auto":
        raise MermaidDiagramError("direction_mode must be 'preserve' or 'auto'")

    decision = decide_flowchart_direction(flowchart, direction_rules)
    rankdir: Literal["TB", "LR"] = "LR" if decision.direction == "LR" else "TB"
    return replace(flowchart, rankdir=rankdir)


def _node_degrees(flowchart: MermaidFlowchart) -> tuple[dict[str, int], dict[str, int]]:
    incoming = {node.identifier: 0 for node in flowchart.nodes}
    outgoing = {node.identifier: 0 for node in flowchart.nodes}
    for edge in flowchart.edges:
        outgoing[edge.source] = outgoing.get(edge.source, 0) + 1
        incoming[edge.target] = incoming.get(edge.target, 0) + 1
    return incoming, outgoing


def _is_single_linear_chain(
    flowchart: MermaidFlowchart,
    incoming: dict[str, int],
    outgoing: dict[str, int],
) -> bool:
    node_ids = {node.identifier for node in flowchart.nodes}
    if not node_ids or len(flowchart.edges) != len(node_ids) - 1:
        return False
    if set(incoming) != node_ids or set(outgoing) != node_ids:
        return False
    if any(degree > 1 for degree in incoming.values()) or any(
        degree > 1 for degree in outgoing.values()
    ):
        return False

    adjacency = {node_id: set() for node_id in node_ids}
    for edge in flowchart.edges:
        if edge.source not in adjacency or edge.target not in adjacency:
            return False
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)

    seen = {next(iter(node_ids))}
    pending = list(seen)
    while pending:
        node_id = pending.pop()
        for neighbor in adjacency[node_id] - seen:
            seen.add(neighbor)
            pending.append(neighbor)
    return seen == node_ids


def _source_lines(mermaid_text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for line_number, source_line in enumerate(mermaid_text.splitlines(), start=1):
        stripped = source_line.strip()
        if not stripped:
            continue
        if stripped.startswith("%%{"):
            raise MermaidDiagramError(f"line {line_number}: Mermaid initialization directives are unsupported")
        if stripped.startswith("%%"):
            continue
        for statement in stripped.split(";"):
            text = statement.strip()
            if text:
                lines.append((line_number, text))
    return lines


def _parse_edge_line(
    text: str,
    line_number: int,
    nodes: dict[str, MermaidNode],
    edges: list[MermaidEdge],
) -> None:
    matches = list(_EDGE_RE.finditer(text))
    start = 0
    node_tokens: list[str] = []
    for match in matches:
        node_tokens.append(text[start : match.start()].strip())
        start = match.end()
    node_tokens.append(text[start:].strip())
    if any(not token for token in node_tokens):
        raise MermaidDiagramError(f"line {line_number}: edge is missing a node")

    parsed_nodes = [_parse_node(token, line_number) for token in node_tokens]
    for node in parsed_nodes:
        _upsert_node(nodes, node)
    for index, match in enumerate(matches):
        edges.append(
            MermaidEdge(
                source=parsed_nodes[index].identifier,
                target=parsed_nodes[index + 1].identifier,
                kind=_edge_kind(match.group("arrow")),
                label=match.group("label"),
            )
        )


def _parse_node(token: str, line_number: int) -> MermaidNode:
    match = _NODE_RE.fullmatch(token)
    if match is None:
        raise MermaidDiagramError(f"line {line_number}: unsupported node syntax: {token!r}")
    identifier = match.group("id")
    shape = "box"
    raw_label = None
    for candidate_shape in ("ellipse", "box", "rounded", "diamond"):
        candidate_label = match.group(candidate_shape)
        if candidate_label is not None:
            shape = candidate_shape
            raw_label = candidate_label
            break
    label = _label(raw_label) if raw_label is not None else identifier
    return MermaidNode(identifier=identifier, label=label, shape=shape)


def _label(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1]
    if not normalized:
        raise MermaidDiagramError("node and edge labels must not be empty")
    return normalized


def _upsert_node(nodes: dict[str, MermaidNode], node: MermaidNode) -> None:
    existing = nodes.get(node.identifier)
    if existing is None or node.label != node.identifier:
        nodes[node.identifier] = node


def _edge_kind(arrow: str) -> Literal["arrow", "line", "dotted", "thick"]:
    return {"-->": "arrow", "---": "line", "-.->": "dotted", "==>": "thick"}[arrow]


def _output_format(output_path: Path) -> DiagramFormat:
    output_format = output_path.suffix.lower().removeprefix(".")
    if output_format not in {"svg", "png"}:
        raise MermaidDiagramError("output path must end with .svg or .png")
    return output_format  # type: ignore[return-value]


def _render_payload(flowchart: MermaidFlowchart, output_format: DiagramFormat) -> str | bytes:
    try:
        from graphviz import Digraph
    except ImportError as exc:
        raise MermaidDiagramUnavailable("Python package 'graphviz' is not installed") from exc

    graph = Digraph(name="mermaid_flowchart", engine="dot")
    graph.attr(
        rankdir=flowchart.rankdir,
        bgcolor="#FFFFFF",
        pad="0.18",
        nodesep="0.45",
        ranksep="0.65",
        splines="polyline",
        outputorder="edgesfirst",
    )
    graph.attr(
        "node",
        fontname="sans-serif",
        fontsize="12",
        color="#666666",
        penwidth="1.2",
        margin="0.16,0.10",
    )
    graph.attr(
        "edge",
        fontname="sans-serif",
        fontsize="10",
        color="#666666",
        penwidth="1.1",
        arrowsize="0.75",
    )
    for node in flowchart.nodes:
        graph.node(node.identifier, label=node.label, **_SHAPE_ATTRIBUTES[node.shape])
    for edge in flowchart.edges:
        attributes = _edge_attributes(edge)
        graph.edge(edge.source, edge.target, **attributes)

    try:
        if output_format == "svg":
            return graph.pipe(format="svg", encoding="utf-8", quiet=True)
        return graph.pipe(format="png", quiet=True)
    except OSError as exc:
        raise MermaidDiagramUnavailable(f"Graphviz dot execution failed: {exc}") from exc
    except Exception as exc:
        if exc.__class__.__module__.startswith("graphviz"):
            raise MermaidDiagramUnavailable(f"Graphviz dot execution failed: {exc}") from exc
        raise


def _edge_attributes(edge: MermaidEdge) -> dict[str, str]:
    attributes: dict[str, str] = {}
    if edge.label:
        attributes["label"] = edge.label
    if edge.kind == "line":
        attributes["arrowhead"] = "none"
    elif edge.kind == "dotted":
        attributes["style"] = "dashed"
    elif edge.kind == "thick":
        attributes["penwidth"] = "2.2"
    return attributes
