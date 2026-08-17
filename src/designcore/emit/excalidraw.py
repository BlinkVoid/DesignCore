"""Compile a graph spec plus placements into an .excalidraw document."""

from __future__ import annotations

from typing import Any

from designcore.layout import Placement
from designcore.spec import DiagramSpec

STROKE_WIDTH = {"normal": 1, "primary": 3, "muted": 1}
OPACITY = {"normal": 100, "primary": 100, "muted": 55}


def _base(element_id: str, x: float, y: float, width: float, height: float) -> dict[str, Any]:
    return {
        "id": element_id,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": 1,
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": [],
        "updated": 1,
        "link": None,
        "locked": False,
    }


def _connection_points(
    start: Placement, end: Placement
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Pick the box edges an arrow should leave from and arrive at.

    Derived from where the boxes actually sit rather than assumed
    left-to-right: Graphviz honours `direction`, so under the default `TB` a
    hardcoded right-edge exit sends the arrow diagonally backwards through
    both boxes. Whichever axis the boxes are further apart on wins, so this
    follows the layout for all four directions.
    """
    start_cx, start_cy = start.x + start.width / 2, start.y + start.height / 2
    end_cx, end_cy = end.x + end.width / 2, end.y + end.height / 2
    dx, dy = end_cx - start_cx, end_cy - start_cy

    if abs(dx) >= abs(dy):
        if dx >= 0:
            return (start.x + start.width, start_cy), (end.x, end_cy)
        return (start.x, start_cy), (end.x + end.width, end_cy)
    if dy >= 0:
        return (start_cx, start.y + start.height), (end_cx, end.y)
    return (start_cx, start.y), (end_cx, end.y + end.height)


def emit_excalidraw(spec: DiagramSpec, placements: dict[str, Placement]) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []

    for node in spec.nodes:
        box = placements[node.id]  # KeyError is correct: never invent geometry
        rect = _base(node.id, box.x, box.y, box.width, box.height)
        rect["type"] = "rectangle"
        rect["strokeWidth"] = STROKE_WIDTH[node.emphasis]
        rect["opacity"] = OPACITY[node.emphasis]
        rect["boundElements"] = [{"type": "text", "id": f"{node.id}-label"}]
        elements.append(rect)

        label = _base(f"{node.id}-label", box.x + 8, box.y + box.height / 2 - 10, box.width - 16, 20)
        label["type"] = "text"
        label["text"] = node.label
        label["originalText"] = node.label
        label["fontSize"] = 16
        label["fontFamily"] = 1
        label["textAlign"] = "center"
        label["verticalAlign"] = "middle"
        label["containerId"] = node.id
        elements.append(label)

    for index, edge in enumerate(spec.edges):
        start, end = placements[edge.source], placements[edge.target]
        (x1, y1), (x2, y2) = _connection_points(start, end)
        arrow = _base(f"edge-{index}", x1, y1, x2 - x1, y2 - y1)
        arrow["type"] = "arrow"
        arrow["points"] = [[0, 0], [x2 - x1, y2 - y1]]
        arrow["strokeStyle"] = "dashed" if edge.kind in {"async", "dashed"} else "solid"
        arrow["startBinding"] = {"elementId": edge.source, "focus": 0, "gap": 4}
        arrow["endBinding"] = {"elementId": edge.target, "focus": 0, "gap": 4}
        elements.append(arrow)

        if edge.label:
            label = _base(f"edge-{index}-label", (x1 + x2) / 2 - 30, (y1 + y2) / 2 - 20, 60, 20)
            label["type"] = "text"
            label["text"] = edge.label
            label["originalText"] = edge.label
            label["fontSize"] = 12
            label["fontFamily"] = 1
            label["textAlign"] = "center"
            label["verticalAlign"] = "middle"
            label["containerId"] = None
            elements.append(label)

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "designcore",
        "elements": elements,
        "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
        "files": {},
    }
