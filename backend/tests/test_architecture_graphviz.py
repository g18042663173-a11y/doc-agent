from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _architecture_slide(*, positioned: bool = False, with_edge: bool = False):
    from app.ir.deck_ir import DeckIR

    nodes = [
        {
            "id": "source",
            "text": "输入",
            "type": "primary",
            "position": {"x": 0.25, "y": 0.5} if positioned else None,
        },
        {"id": "target", "text": "输出", "type": "data"},
    ]
    edges = [{"from": "source", "to": "target"}] if with_edge else []
    deck = DeckIR.model_validate(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "Graphviz failure tests", "theme": "hw_v1"},
            "slides": [
                {
                    "layout": "architecture_diagram",
                    "title": "架构图",
                    "nodes": nodes,
                    "edges": edges,
                    "groups": [],
                }
            ],
        }
    )
    return deck.slides[0]


def test_graphviz_layout_rejects_manual_geometry_for_deterministic_fallback() -> None:
    from app.rendering.architecture_graphviz import GraphvizLayoutUnavailable, layout_architecture_with_graphviz
    from app.rendering.theme import load_theme

    theme = load_theme("hw_v1")
    with pytest.raises(GraphvizLayoutUnavailable, match="manual position/size hints"):
        layout_architecture_with_graphviz(
            _architecture_slide(positioned=True),
            theme["layouts"]["architecture_diagram"],
            theme,
        )


def test_graphviz_layout_helpers_reject_invalid_geometry() -> None:
    from app.rendering.architecture_graphviz import (
        _CoordinateTransform,
        _coordinate_transform,
        _edge_index,
        _edge_layout,
        _parse_numbers,
    )
    from app.rendering.theme import load_theme

    theme = load_theme("hw_v1")
    layout = theme["layouts"]["architecture_diagram"]
    with pytest.raises(ValueError, match="invalid graph bounding box"):
        _coordinate_transform("0,0,0,72", layout["content"], layout)
    with pytest.raises(ValueError, match="unexpected edge id"):
        _edge_index({"id": "unknown"})
    with pytest.raises(ValueError, match="expected 2 numbers"):
        _parse_numbers("1,2,3", expected=2)
    with pytest.raises(ValueError, match="has no usable route"):
        _edge_layout(
            {"id": "edge_1", "_draw_": []},
            _CoordinateTransform(0, 72, 1, 0, 0),
            {1: None},
            layout,
        )


class _FakeDigraph:
    payload: str | None = None
    error: Exception | None = None

    def __init__(self, **_kwargs) -> None:
        pass

    def attr(self, *_args, **_kwargs) -> None:
        pass

    def node(self, *_args, **_kwargs) -> None:
        pass

    def edge(self, *_args, **_kwargs) -> None:
        pass

    def pipe(self, **_kwargs) -> str:
        if self.error is not None:
            raise self.error
        assert self.payload is not None
        return self.payload


def test_graphviz_layout_reports_dot_execution_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import graphviz

    from app.rendering.architecture_graphviz import GraphvizLayoutUnavailable, layout_architecture_with_graphviz
    from app.rendering.theme import load_theme

    _FakeDigraph.error = OSError("dot missing")
    _FakeDigraph.payload = None
    monkeypatch.setattr(graphviz, "Digraph", _FakeDigraph)
    theme = load_theme("hw_v1")
    with pytest.raises(GraphvizLayoutUnavailable, match="dot execution failed: dot missing"):
        layout_architecture_with_graphviz(
            _architecture_slide(),
            theme["layouts"]["architecture_diagram"],
            theme,
        )
    _FakeDigraph.error = None


def test_graphviz_layout_reports_graphviz_runtime_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import graphviz
    from graphviz.backend import ExecutableNotFound

    from app.rendering.architecture_graphviz import GraphvizLayoutUnavailable, layout_architecture_with_graphviz
    from app.rendering.theme import load_theme

    _FakeDigraph.error = ExecutableNotFound(["dot"])
    _FakeDigraph.payload = None
    monkeypatch.setattr(graphviz, "Digraph", _FakeDigraph)
    theme = load_theme("hw_v1")
    with pytest.raises(GraphvizLayoutUnavailable, match="dot execution failed"):
        layout_architecture_with_graphviz(
            _architecture_slide(),
            theme["layouts"]["architecture_diagram"],
            theme,
        )
    _FakeDigraph.error = None


def test_graphviz_layout_rejects_incomplete_node_results(monkeypatch: pytest.MonkeyPatch) -> None:
    import graphviz

    from app.rendering.architecture_graphviz import GraphvizLayoutUnavailable, layout_architecture_with_graphviz
    from app.rendering.theme import load_theme

    _FakeDigraph.error = None
    _FakeDigraph.payload = json.dumps({"bb": "0,0,144,72", "objects": [], "edges": []})
    monkeypatch.setattr(graphviz, "Digraph", _FakeDigraph)
    theme = load_theme("hw_v1")
    with pytest.raises(GraphvizLayoutUnavailable, match="dot returned incomplete layout data"):
        layout_architecture_with_graphviz(
            _architecture_slide(),
            theme["layouts"]["architecture_diagram"],
            theme,
        )


def test_graphviz_layout_rejects_missing_edge_results(monkeypatch: pytest.MonkeyPatch) -> None:
    import graphviz

    from app.rendering.architecture_graphviz import GraphvizLayoutUnavailable, layout_architecture_with_graphviz
    from app.rendering.theme import load_theme

    _FakeDigraph.error = None
    _FakeDigraph.payload = json.dumps(
        {
            "bb": "0,0,144,72",
            "objects": [
                {"name": "node_0", "pos": "36,36", "width": 0.8, "height": 0.5},
                {"name": "node_1", "pos": "108,36", "width": 0.8, "height": 0.5},
            ],
            "edges": [],
        }
    )
    monkeypatch.setattr(graphviz, "Digraph", _FakeDigraph)
    theme = load_theme("hw_v1")
    with pytest.raises(GraphvizLayoutUnavailable, match="did not return every architecture edge"):
        layout_architecture_with_graphviz(
            _architecture_slide(with_edge=True),
            theme["layouts"]["architecture_diagram"],
            theme,
        )
