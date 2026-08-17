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
        x1, y1 = start.x + start.width, start.y + start.height / 2
        x2, y2 = end.x, end.y + end.height / 2
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
