"""Geometry comes from Graphviz. The model never supplies coordinates."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

from designcore.render import BackendMissing, RenderError
from designcore.spec import DIRECTIONS, DiagramSpec

DPI = 72.0
INSTALL_HINT = "sudo apt install graphviz"


@dataclass(frozen=True)
class Placement:
    id: str
    x: float
    y: float
    width: float
    height: float


def _quote(value: str) -> str:
    """Escape a string for a DOT double-quoted ID.

    spec.py puts no charset restriction on labels, so a quote that the
    mermaid emitter happily escapes would otherwise reach dot unescaped and
    fail the whole layout with a syntax error.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def to_dot(spec: DiagramSpec) -> str:
    # Passed through rather than folded to LR/TB: Graphviz supports all four,
    # and Mermaid honours RL/BT, so collapsing them here would lay the same
    # spec out in opposite directions depending on the output format.
    rankdir = spec.direction.upper() if spec.direction.upper() in DIRECTIONS else "TB"
    lines = [f"digraph {spec.id.replace('-', '_')} {{", f"  rankdir={rankdir};", "  node [shape=box];"]
    grouped = {m for g in spec.groups for m in g.members}

    for group in spec.groups:
        lines.append(f"  subgraph cluster_{group.id} {{")
        lines.append(f'    label="{_quote(group.label)}";')
        for member in group.members:
            node = next(n for n in spec.nodes if n.id == member)
            lines.append(f'    "{_quote(node.id)}" [label="{_quote(node.label)}"];')
        lines.append("  }")

    for node in spec.nodes:
        if node.id not in grouped:
            lines.append(f'  "{_quote(node.id)}" [label="{_quote(node.label)}"];')

    for edge in spec.edges:
        # The label is declared so Graphviz reserves rank separation for it.
        # Without it adjacent nodes sit close enough that a renderer's opaque
        # edge label covers the arrow completely -- the drawio export of the
        # Task 14 example had two edges with no visible line at all.
        attributes = f' [label="{_quote(edge.label)}"]' if edge.label else ""
        lines.append(f'  "{_quote(edge.source)}" -> "{_quote(edge.target)}"{attributes};')

    lines.append("}")
    return "\n".join(lines) + "\n"


def _run_dot(
    spec: DiagramSpec,
    run: Callable[..., subprocess.CompletedProcess],
    which: Callable[[str], str | None],
) -> dict:
    """Lay the spec out with Graphviz and return the parsed -Tjson document."""
    if which("dot") is None:
        raise BackendMissing(
            f"graphviz (dot) is not installed, so node geometry cannot be computed. "
            f"Install it with: {INSTALL_HINT}"
        )
    result = run(["dot", "-Tjson"], input=to_dot(spec), capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderError(f"dot failed for spec {spec.id}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _canvas_height(data: dict) -> float:
    return float(data["bb"].split(",")[3])


Route = tuple[tuple[float, float], ...]


def layout_all(
    spec: DiagramSpec,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[dict[str, Placement], dict[str, Placement], dict[tuple[str, str], Route]]:
    """Return (node placements, group boxes, edge routes) from one Graphviz run.

    Callers needing more than one -- the drawio and excalidraw emitters do --
    should use this rather than calling the individual functions: one dot
    invocation instead of three, and the results provably describe the same
    layout.
    """
    data = _run_dot(spec, run, which)
    return _placements(spec, data), _group_boxes(spec, data), _edge_routes(data)


def layout_edges(
    spec: DiagramSpec,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> dict[tuple[str, str], Route]:
    """Return each edge's routed path, keyed by (source, target).

    Graphviz routes every edge as a bezier that avoids the nodes in its way.
    Throwing that away leaves emitters drawing straight point-to-point lines
    that cut through whatever sits between the endpoints.
    """
    return _edge_routes(_run_dot(spec, run, which))


def _edge_routes(data: dict) -> dict[tuple[str, str], Route]:
    canvas_height = _canvas_height(data)
    names = {
        obj.get("_gvid"): obj.get("name", "")
        for obj in data.get("objects", [])
        if "_gvid" in obj
    }

    routes: dict[tuple[str, str], Route] = {}
    for edge in data.get("edges", []):
        source, target = names.get(edge.get("tail")), names.get(edge.get("head"))
        position = edge.get("pos")
        if not source or not target or not position:
            continue
        key = (source, target)
        if key in routes:
            continue  # parallel edges share a route; the first one wins
        routes[key] = _parse_spline(position, canvas_height)
    return routes


def _parse_spline(position: str, canvas_height: float) -> Route:
    """Parse Graphviz's spline syntax into top-left pixel points.

    The form is `e,<tip> <p0> <p1> ...`: the `e,` token is the arrowhead tip
    and belongs at the end of the path, not the start where it is written.
    """
    tip: tuple[float, float] | None = None
    points: list[tuple[float, float]] = []
    for token in position.split():
        prefix, _, raw = token.partition(",") if token[:2] in ("e,", "s,") else ("", "", token)
        try:
            x_text, y_text = (raw or token).split(",")
            point = (float(x_text), canvas_height - float(y_text))
        except ValueError:
            continue
        if prefix == "e":
            tip = point
        elif prefix != "s":
            points.append(point)
    if tip is not None:
        points.append(tip)
    return tuple(points)


def layout_spec(
    spec: DiagramSpec,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> dict[str, Placement]:
    """Return top-left-origin pixel placements keyed by node id."""
    return _placements(spec, _run_dot(spec, run, which))


def _placements(spec: DiagramSpec, data: dict) -> dict[str, Placement]:
    canvas_height = _canvas_height(data)
    node_ids = {n.id for n in spec.nodes}

    placements: dict[str, Placement] = {}
    for obj in data.get("objects", []):
        name = obj.get("name", "")
        if name not in node_ids:
            continue  # clusters and anything else Graphviz reports
        cx, cy = (float(v) for v in obj["pos"].split(","))
        width = float(obj["width"]) * DPI
        height = float(obj["height"]) * DPI
        placements[name] = Placement(
            id=name,
            x=cx - width / 2,
            y=canvas_height - cy - height / 2,
            width=width,
            height=height,
        )
    return placements


def layout_groups(
    spec: DiagramSpec,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> dict[str, Placement]:
    """Return each group's bounding box, keyed by group id (amendment A2).

    Graphviz reports a cluster as `bb: "x1,y1,x2,y2"` in points with a
    bottom-left origin; converted here to the same top-left pixel convention
    as layout_spec so emitters need no coordinate maths.
    """
    return _group_boxes(spec, _run_dot(spec, run, which))


def _group_boxes(spec: DiagramSpec, data: dict) -> dict[str, Placement]:
    canvas_height = _canvas_height(data)
    by_cluster_name = {f"cluster_{group.id}": group.id for group in spec.groups}

    boxes: dict[str, Placement] = {}
    for obj in data.get("objects", []):
        group_id = by_cluster_name.get(obj.get("name", ""))
        if group_id is None or "bb" not in obj:
            continue
        x1, y1, x2, y2 = (float(v) for v in obj["bb"].split(","))
        boxes[group_id] = Placement(
            id=group_id,
            x=x1,
            y=canvas_height - y2,
            width=x2 - x1,
            height=y2 - y1,
        )
    return boxes
