from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
import unicodedata

from app.ir.deck_ir import ArchitectureDiagramSlide


POINTS_PER_INCH = 72.0


class GraphvizLayoutUnavailable(RuntimeError):
    """Raised when Graphviz cannot produce a usable architecture layout."""


@dataclass(frozen=True)
class ArchitectureEdgeLayout:
    edge_index: int
    points: tuple[tuple[float, float], ...]
    label_text: str | None
    label_box: dict[str, float] | None


@dataclass(frozen=True)
class ArchitectureGraphvizLayout:
    node_boxes: dict[str, dict[str, float]]
    node_texts: dict[str, str]
    group_layers: tuple[tuple[str, str, list[str], dict[str, float]], ...]
    edges: tuple[ArchitectureEdgeLayout, ...]
    node_font_size_pt: float


@dataclass(frozen=True)
class _CoordinateTransform:
    lower_x: float
    upper_y: float
    scale: float
    offset_x_in: float
    offset_y_in: float

    def point(self, x: float, y: float) -> tuple[float, float]:
        return (
            self.offset_x_in + (x - self.lower_x) / POINTS_PER_INCH * self.scale,
            self.offset_y_in + (self.upper_y - y) / POINTS_PER_INCH * self.scale,
        )

    def size(self, width_points: float, height_points: float) -> tuple[float, float]:
        return (
            width_points / POINTS_PER_INCH * self.scale,
            height_points / POINTS_PER_INCH * self.scale,
        )


def layout_architecture_with_graphviz(
    slide_ir: ArchitectureDiagramSlide,
    layout: dict,
    theme: dict,
) -> ArchitectureGraphvizLayout:
    if _has_manual_geometry(slide_ir):
        raise GraphvizLayoutUnavailable("manual position/size hints require the deterministic fallback")

    try:
        from graphviz import Digraph
    except ImportError as exc:
        raise GraphvizLayoutUnavailable("Python package 'graphviz' is not installed") from exc

    graph = Digraph(name="architecture", engine="dot", format="json")
    graph.attr(
        rankdir=layout["graphviz_rankdir"],
        splines="ortho",
        compound="true",
        newrank="true",
        outputorder="edgesfirst",
        nodesep=str(layout["graphviz_node_sep_in"]),
        ranksep=str(layout["graphviz_rank_sep_in"]),
        pad=str(layout["graphviz_graph_padding_in"]),
        margin="0",
    )
    graph.attr(
        "node",
        shape="box",
        style="rounded",
        fixedsize="false",
        fontname=theme["fonts"]["east_asia"][0],
        fontsize=str(layout["node_font_size_pt"]),
        margin=(
            f'{layout["graphviz_node_horizontal_margin_in"]},'
            f'{layout["graphviz_node_vertical_margin_in"]}'
        ),
        width=str(layout["node_min_width_in"]),
        height=str(layout["node_min_height_in"]),
    )
    graph.attr(
        "edge",
        fontname=theme["fonts"]["east_asia"][0],
        fontsize=str(layout["edge_label_font_size_pt"]),
        labelfloat="false",
        minlen=str(layout["graphviz_edge_minlen"]),
        dir="none",
    )

    node_names = {node.id: f"node_{index}" for index, node in enumerate(slide_ir.nodes)}
    node_texts = {
        node.id: _wrap_label(node.text, layout["graphviz_node_wrap_units"])
        for node in slide_ir.nodes
    }
    grouped_node_ids: set[str] = set()
    for group_index, group in enumerate(slide_ir.groups):
        grouped_node_ids.update(group.node_ids)
        with graph.subgraph(name=f"cluster_{group_index}") as cluster:
            cluster.attr(
                label=group.label,
                fontname=theme["fonts"]["east_asia"][0],
                fontsize=str(layout["group_label_font_size_pt"]),
                margin=str(layout["graphviz_cluster_margin_pt"]),
            )
            for node_id in group.node_ids:
                cluster.node(node_names[node_id], node_texts[node_id])
    for node in slide_ir.nodes:
        if node.id not in grouped_node_ids:
            graph.node(node_names[node.id], node_texts[node.id])

    edge_label_texts: dict[int, str | None] = {}
    for edge_index, edge in enumerate(slide_ir.edges, start=1):
        label = _wrap_label(edge.label, layout["graphviz_edge_label_wrap_units"]) if edge.label else None
        edge_label_texts[edge_index] = label
        attributes = {"id": f"edge_{edge_index}"}
        if label:
            attributes["label"] = label
        graph.edge(node_names[edge.from_node], node_names[edge.to], **attributes)

    try:
        # Keep Graphviz streams binary. On localized Windows installations dot
        # can emit non-UTF-8 font diagnostics on stderr; asking graphviz for
        # text mode causes its reader thread to fail before we can safely fall
        # back to the deterministic layout.
        payload = graph.pipe(encoding=None, quiet=True)
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        data = json.loads(payload)
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GraphvizLayoutUnavailable(f"dot execution failed: {exc}") from exc
    except Exception as exc:
        if exc.__class__.__module__.startswith("graphviz"):
            raise GraphvizLayoutUnavailable(f"dot execution failed: {exc}") from exc
        raise

    try:
        transform = _coordinate_transform(data["bb"], layout["content"], layout)
        objects_by_name = {item["name"]: item for item in data["objects"]}
        node_boxes = {
            node.id: _node_box(objects_by_name[node_names[node.id]], transform)
            for node in slide_ir.nodes
        }
        group_layers = tuple(
            (
                group.id,
                group.label,
                list(group.node_ids),
                _bounding_box(objects_by_name[f"cluster_{index}"]["bb"], transform),
            )
            for index, group in enumerate(slide_ir.groups)
        )
        edges = tuple(
            _edge_layout(item, transform, edge_label_texts, layout)
            for item in sorted(data.get("edges", []), key=_edge_index)
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GraphvizLayoutUnavailable(f"dot returned incomplete layout data: {exc}") from exc

    expected_edges = set(range(1, len(slide_ir.edges) + 1))
    actual_edges = {edge.edge_index for edge in edges}
    if actual_edges != expected_edges:
        raise GraphvizLayoutUnavailable("dot did not return every architecture edge")

    font_scale = min(transform.scale, 1.0)
    node_font_size = (
        layout["node_font_size_pt"]
        if font_scale >= layout["graphviz_preserve_node_font_scale"]
        else max(
            layout["graphviz_min_node_font_size_pt"],
            layout["node_font_size_pt"] * font_scale,
        )
    )
    return ArchitectureGraphvizLayout(
        node_boxes=node_boxes,
        node_texts=node_texts,
        group_layers=group_layers,
        edges=edges,
        node_font_size_pt=node_font_size,
    )


def _has_manual_geometry(slide_ir: ArchitectureDiagramSlide) -> bool:
    if any(node.position is not None or node.size is not None for node in slide_ir.nodes):
        return True
    hints = slide_ir.manual_hints
    return bool(hints and (hints.node_positions or hints.node_sizes))


def _coordinate_transform(bb: str, content: dict, layout: dict) -> _CoordinateTransform:
    lower_x, lower_y, upper_x, upper_y = _parse_numbers(bb, expected=4)
    graph_width_in = (upper_x - lower_x) / POINTS_PER_INCH
    graph_height_in = (upper_y - lower_y) / POINTS_PER_INCH
    if graph_width_in <= 0 or graph_height_in <= 0:
        raise ValueError("invalid graph bounding box")

    padding = layout["graphviz_content_padding_in"]
    available_width = content["width_in"] - padding * 2
    available_height = content["height_in"] - padding * 2
    scale = min(
        available_width / graph_width_in,
        available_height / graph_height_in,
        layout["graphviz_max_scale"],
    )
    rendered_width = graph_width_in * scale
    rendered_height = graph_height_in * scale
    return _CoordinateTransform(
        lower_x=lower_x,
        upper_y=upper_y,
        scale=scale,
        offset_x_in=content["left_in"] + padding + (available_width - rendered_width) / 2,
        offset_y_in=content["top_in"] + padding + (available_height - rendered_height) / 2,
    )


def _node_box(item: dict, transform: _CoordinateTransform) -> dict[str, float]:
    center_x, center_y = _parse_numbers(item["pos"], expected=2)
    center = transform.point(center_x, center_y)
    width = float(item["width"]) * transform.scale
    height = float(item["height"]) * transform.scale
    return {
        "left_in": center[0] - width / 2,
        "top_in": center[1] - height / 2,
        "width_in": width,
        "height_in": height,
    }


def _bounding_box(bb: str, transform: _CoordinateTransform) -> dict[str, float]:
    lower_x, lower_y, upper_x, upper_y = _parse_numbers(bb, expected=4)
    left, top = transform.point(lower_x, upper_y)
    width, height = transform.size(upper_x - lower_x, upper_y - lower_y)
    return {"left_in": left, "top_in": top, "width_in": width, "height_in": height}


def _edge_layout(
    item: dict,
    transform: _CoordinateTransform,
    label_texts: dict[int, str | None],
    layout: dict,
) -> ArchitectureEdgeLayout:
    edge_index = _edge_index(item)
    graph_points: list[tuple[float, float]] = []
    for operation in item.get("_draw_", []):
        if operation.get("op") not in {"b", "L"}:
            continue
        for raw_point in operation.get("points", []):
            point = (float(raw_point[0]), float(raw_point[1]))
            if not graph_points or point != graph_points[-1]:
                graph_points.append(point)
    if len(graph_points) < 2:
        raise ValueError(f"edge {edge_index} has no usable route")
    points = tuple(transform.point(x, y) for x, y in graph_points)
    label_text = label_texts[edge_index]
    label_box = _edge_label_box(item, transform, layout) if label_text else None
    return ArchitectureEdgeLayout(edge_index, points, label_text, label_box)


def _edge_label_box(item: dict, transform: _CoordinateTransform, layout: dict) -> dict[str, float]:
    center_x, center_y = _parse_numbers(item["lp"], expected=2)
    text_operations = [operation for operation in item.get("_ldraw_", []) if operation.get("op") == "T"]
    graph_width = max((float(operation.get("width", 0)) for operation in text_operations), default=0)
    font_size = max((float(operation.get("size", layout["edge_label_font_size_pt"])) for operation in text_operations), default=layout["edge_label_font_size_pt"])
    line_count = max(len(text_operations), 1)
    graph_height = font_size * layout["graphviz_label_line_height"] * line_count
    width, height = transform.size(graph_width, graph_height)
    horizontal_margin = layout["graphviz_label_horizontal_margin_in"]
    vertical_margin = layout["graphviz_label_vertical_margin_in"]
    width = max(
        width + horizontal_margin * 2 + layout["graphviz_label_width_safety_in"],
        layout["graphviz_label_min_width_in"],
    )
    height = max(height + vertical_margin * 2, layout["graphviz_label_min_height_in"])
    center = transform.point(center_x, center_y)
    return {
        "left_in": center[0] - width / 2,
        "top_in": center[1] - height / 2,
        "width_in": width,
        "height_in": height,
    }


def _edge_index(item: dict) -> int:
    identifier = str(item["id"])
    if not identifier.startswith("edge_"):
        raise ValueError(f"unexpected edge id: {identifier}")
    return int(identifier.removeprefix("edge_"))


def _parse_numbers(value: str, *, expected: int) -> tuple[float, ...]:
    numbers = tuple(float(part) for part in str(value).split(","))
    if len(numbers) != expected:
        raise ValueError(f"expected {expected} numbers, got {value!r}")
    return numbers


def _wrap_label(text: str, max_units: int) -> str:
    wrapped_lines: list[str] = []
    for source_line in str(text).splitlines() or [""]:
        current = ""
        current_units = 0
        for character in source_line:
            width = 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
            if current and current_units + width > max_units:
                wrapped_lines.append(current.rstrip())
                current = character.lstrip()
                current_units = width if current else 0
            else:
                current += character
                current_units += width
        wrapped_lines.append(current.rstrip())
    return "\n".join(wrapped_lines)
