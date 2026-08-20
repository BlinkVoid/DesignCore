"""Compile a graph spec plus placements into an .excalidraw document."""

from __future__ import annotations

import zlib
from typing import Any

from designcore.layout import Placement
from designcore.spec import DiagramSpec

EDGE_FONT_SIZE = 12
STROKE_WIDTH = {"normal": 1, "primary": 3, "muted": 1}
OPACITY = {"normal": 100, "primary": 100, "muted": 55}

# Excalidraw's own palette. Roles get a colour and a fill so a scene reads as
# a sketch rather than a wireframe; `external` stays unfilled and dashed to
# match the convention the mermaid and drawio emitters use for things outside
# the system boundary.
ROLE_STYLE: dict[str, dict[str, str]] = {
    "actor": {"strokeColor": "#1971c2", "backgroundColor": "#a5d8ff", "strokeStyle": "solid"},
    "service": {"strokeColor": "#1e1e1e", "backgroundColor": "#e9ecef", "strokeStyle": "solid"},
    "store": {"strokeColor": "#2f9e44", "backgroundColor": "#b2f2bb", "strokeStyle": "solid"},
    "infra": {"strokeColor": "#6741d9", "backgroundColor": "#d0bfff", "strokeStyle": "solid"},
    "external": {
        "strokeColor": "#868e96",
        "backgroundColor": "transparent",
        "strokeStyle": "dashed",
    },
    "note": {"strokeColor": "#f08c00", "backgroundColor": "#ffec99", "strokeStyle": "solid"},
}
DEFAULT_ROLE_STYLE = ROLE_STYLE["service"]

# A boundary, not a shape: unfilled and dashed so it reads as an enclosure
# rather than competing with the nodes inside it.
GROUP_STYLE = {
    "strokeColor": "#868e96",
    "backgroundColor": "transparent",
    "strokeStyle": "dashed",
    "fillStyle": "hachure",
}


def _seed(element_id: str) -> int:
    """A stable per-element seed.

    rough.js derives its hand-drawn jitter from this, so a single shared seed
    makes every shape wobble identically and the scene reads as mechanically
    repeated rather than drawn. crc32 keeps it varied but deterministic --
    Python's hash() is salted per process and would change every render.
    """
    return zlib.crc32(element_id.encode("utf-8")) & 0x7FFFFFFF


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
        "seed": _seed(element_id),
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

    Chosen by which axis actually *separates* the two boxes, not by which
    centre delta is larger. In a layered TB graph two boxes routinely overlap
    horizontally while sitting on different ranks, and their centres can still
    be further apart on x -- judging by centre distance then exits the right
    edge and drags the arrow backwards across the diagram. Separation is the
    property that matters: an arrow can only leave cleanly on an axis where
    there is a gap.
    """
    start_cx, start_cy = start.x + start.width / 2, start.y + start.height / 2
    end_cx, end_cy = end.x + end.width / 2, end.y + end.height / 2
    dx, dy = end_cx - start_cx, end_cy - start_cy

    separated_x = end.x >= start.x + start.width or end.x + end.width <= start.x
    separated_y = end.y >= start.y + start.height or end.y + end.height <= start.y

    if separated_x and not separated_y:
        horizontal = True
    elif separated_y and not separated_x:
        horizontal = False
    else:
        # Both axes separated (a diagonal neighbour) or neither (overlapping
        # boxes): fall back to the dominant direction of travel.
        horizontal = abs(dx) >= abs(dy)

    if horizontal:
        if dx >= 0:
            return (start.x + start.width, start_cy), (end.x, end_cy)
        return (start.x, start_cy), (end.x + end.width, end_cy)
    if dy >= 0:
        return (start_cx, start.y + start.height), (end_cx, end.y)
    return (start_cx, start.y), (end_cx, end.y + end.height)


def emit_excalidraw(
    spec: DiagramSpec,
    placements: dict[str, Placement],
    routes: dict[tuple[str, str], tuple[tuple[float, float], ...]] | None = None,
    groups: dict[str, Placement] | None = None,
) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []

    # Groups first: Excalidraw paints in array order, so a container declared
    # after its members would cover them.
    for group in spec.groups:
        box = (groups or {}).get(group.id)
        if box is None:
            continue  # no geometry computed for this group; skip rather than invent
        frame = _base(group.id, box.x, box.y, box.width, box.height)
        frame["type"] = "rectangle"
        frame["roundness"] = {"type": 3}
        frame.update(GROUP_STYLE)
        elements.append(frame)

        if group.label:
            caption = _base(f"{group.id}-caption", box.x + 12, box.y + 6, box.width - 24, 18)
            caption["type"] = "text"
            caption["text"] = group.label
            caption["originalText"] = group.label
            caption["fontSize"] = 14
            caption["fontFamily"] = 1
            caption["textAlign"] = "left"
            caption["verticalAlign"] = "top"
            caption["strokeColor"] = GROUP_STYLE["strokeColor"]
            caption["containerId"] = None
            elements.append(caption)

    for node in spec.nodes:
        box = placements[node.id]  # KeyError is correct: never invent geometry
        rect = _base(node.id, box.x, box.y, box.width, box.height)
        rect["type"] = "rectangle"
        rect["roundness"] = {"type": 3}  # how Excalidraw draws a rectangle
        rect["fillStyle"] = "hachure"    # the sketchy fill, not a flat block
        rect.update(ROLE_STYLE.get(node.role, DEFAULT_ROLE_STYLE))
        rect["strokeWidth"] = STROKE_WIDTH[node.emphasis]
        rect["opacity"] = OPACITY[node.emphasis]
        rect["boundElements"] = [{"type": "text", "id": f"{node.id}-label"}]
        elements.append(rect)

        label_height = box.height - 16
        label = _base(f"{node.id}-label", box.x + 8, box.y + 8, box.width - 16, label_height)
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
        route = (routes or {}).get((edge.source, edge.target))

        if route and len(route) >= 2:
            # Graphviz already routed this edge around whatever is in the way;
            # following it beats a straight line through the obstacles.
            (x1, y1), (x2, y2) = route[0], route[-1]
            points = [[px - x1, py - y1] for px, py in route]
        else:
            (x1, y1), (x2, y2) = _connection_points(start, end)
            points = [[0, 0], [x2 - x1, y2 - y1]]

        arrow = _base(f"edge-{index}", x1, y1, x2 - x1, y2 - y1)
        arrow["type"] = "arrow"
        arrow["points"] = points
        if route and len(route) > 2:
            arrow["roundness"] = {"type": 2}  # smooth the bezier, not a polyline
        arrow["strokeStyle"] = "dashed" if edge.kind in {"async", "dashed"} else "solid"
        arrow["startArrowhead"] = None
        arrow["endArrowhead"] = "arrow"
        arrow["startBinding"] = {"elementId": edge.source, "focus": 0, "gap": 4}
        arrow["endBinding"] = {"elementId": edge.target, "focus": 0, "gap": 4}
        elements.append(arrow)

        if edge.label:
            # Sized from the text: exportToSvg derives the scene bounding box
            # from declared width/height, so a label that overflows its box
            # gets cropped out of the SVG and PNG near the canvas edge.
            width = max(len(edge.label) * EDGE_FONT_SIZE * 0.6, 24.0)
            label = _base(
                f"edge-{index}-label",
                (x1 + x2) / 2 - width / 2,
                (y1 + y2) / 2 - 20,
                width,
                20,
            )
            label["type"] = "text"
            label["text"] = edge.label
            label["originalText"] = edge.label
            label["fontSize"] = EDGE_FONT_SIZE
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
