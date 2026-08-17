"""Compile a graph spec plus placements into editable mxGraph XML.

DesignCore owns this emitter outright (amendment A1). The `@drawio/mcp`
conversion path was retired after the Task 2 probe showed it opens a browser
editor rather than returning XML, so geometry comes from Graphviz exactly as
it does for the Excalidraw emitter -- never from the spec.

The document is built with ElementTree rather than string concatenation so
that labels containing `&`, `<` or `>` are escaped by construction. That is
the XML half of amendment A8's warning about unescaped labels.
"""

from __future__ import annotations

import html
from xml.etree import ElementTree

from designcore.layout import Placement
from designcore.spec import DiagramSpec

EMPHASIS_STYLE = {"normal": "", "primary": "strokeWidth=3;", "muted": "opacity=55;"}
ROLE_STYLE = {
    "actor": "shape=umlActor;",
    "service": "rounded=1;",
    "store": "shape=cylinder3;",
    "infra": "rounded=0;",
    "external": "rounded=0;dashed=1;",
    "note": "shape=note;",
}
EDGE_STYLE = {
    "sync": "edgeStyle=orthogonalEdgeStyle;html=1;",
    "async": "edgeStyle=orthogonalEdgeStyle;html=1;dashed=1;",
    "data": "edgeStyle=orthogonalEdgeStyle;html=1;strokeWidth=2;",
    "dashed": "edgeStyle=orthogonalEdgeStyle;html=1;dashed=1;",
}
GROUP_STYLE = "rounded=0;dashed=1;fillColor=none;verticalAlign=top;align=left;spacing=8;"

ROOT_ID = "1"


def _label(value: str) -> str:
    """HTML-escape a label, because every cell we emit declares `html=1`.

    ElementTree escapes this again for XML on the way out, so the file holds
    `&amp;lt;` and draw.io's HTML parser renders a literal `<`. Skipping this
    step keeps the XML well formed but silently drops anything that looks
    like a tag -- a real render swallowed `<fast>` entirely.
    """
    return html.escape(value, quote=False)


def _number(value: float) -> str:
    """Render a coordinate the way mxGraph expects: no trailing .0 noise."""
    return str(int(value)) if float(value).is_integer() else str(float(value))


def _geometry(parent: ElementTree.Element, box: Placement) -> None:
    ElementTree.SubElement(
        parent,
        "mxGeometry",
        {
            "x": _number(box.x),
            "y": _number(box.y),
            "width": _number(box.width),
            "height": _number(box.height),
            "as": "geometry",
        },
    )


def emit_drawio(
    spec: DiagramSpec,
    placements: dict[str, Placement],
    groups: dict[str, Placement] | None = None,
) -> str:
    """Return an mxfile document placing every node at its computed geometry."""
    groups = groups or {}

    mxfile = ElementTree.Element("mxfile", {"host": "designcore"})
    diagram = ElementTree.SubElement(mxfile, "diagram", {"name": spec.title, "id": spec.id})
    model = ElementTree.SubElement(diagram, "mxGraphModel")
    root = ElementTree.SubElement(model, "root")

    ElementTree.SubElement(root, "mxCell", {"id": "0"})
    ElementTree.SubElement(root, "mxCell", {"id": ROOT_ID, "parent": "0"})

    # Groups first: mxGraph paints in document order, so a container declared
    # after its members would cover them.
    for group in spec.groups:
        box = groups.get(group.id)
        if box is None:
            continue  # no geometry computed for this group; skip rather than invent
        cell = ElementTree.SubElement(
            root,
            "mxCell",
            {
                "id": group.id,
                "value": _label(group.label),
                "style": GROUP_STYLE,
                "vertex": "1",
                "parent": ROOT_ID,
            },
        )
        _geometry(cell, box)

    for node in spec.nodes:
        box = placements[node.id]  # KeyError is correct: never invent geometry
        style = ROLE_STYLE.get(node.role, "") + EMPHASIS_STYLE.get(node.emphasis, "")
        cell = ElementTree.SubElement(
            root,
            "mxCell",
            {
                "id": node.id,
                "value": _label(node.label),
                "style": f"whiteSpace=wrap;html=1;{style}",
                "vertex": "1",
                "parent": ROOT_ID,
            },
        )
        _geometry(cell, box)

    for index, edge in enumerate(spec.edges):
        cell = ElementTree.SubElement(
            root,
            "mxCell",
            {
                "id": f"edge-{index}",
                "value": _label(edge.label),
                "style": EDGE_STYLE.get(edge.kind, EDGE_STYLE["sync"]),
                "edge": "1",
                "parent": ROOT_ID,
                "source": edge.source,
                "target": edge.target,
            },
        )
        ElementTree.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})

    return ElementTree.tostring(mxfile, encoding="unicode")
