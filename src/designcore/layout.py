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


def layout_spec(
    spec: DiagramSpec,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> dict[str, Placement]:
    """Return top-left-origin pixel placements keyed by node id."""
    data = _run_dot(spec, run, which)
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
    data = _run_dot(spec, run, which)
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
