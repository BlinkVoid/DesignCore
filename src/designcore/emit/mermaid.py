"""Compile a graph spec to Mermaid flowchart source."""

from __future__ import annotations

from designcore.spec import DiagramSpec

ARROWS = {"sync": "-->", "async": "-.->", "data": "==>", "dashed": "-.->"}


def _escape(label: str) -> str:
    return label.replace('"', "&quot;")


def emit_mermaid(spec: DiagramSpec) -> str:
    lines = [f"flowchart {spec.direction}"]
    grouped = {member for group in spec.groups for member in group.members}

    for group in spec.groups:
        lines.append(f'    subgraph {group.id}["{_escape(group.label)}"]')
        for member in group.members:
            node = next(n for n in spec.nodes if n.id == member)
            lines.append(f'        {node.id}["{_escape(node.label)}"]')
        lines.append("    end")

    for node in spec.nodes:
        if node.id not in grouped:
            lines.append(f'    {node.id}["{_escape(node.label)}"]')

    for edge in spec.edges:
        arrow = ARROWS[edge.kind]
        if edge.label:
            lines.append(f"    {edge.source} {arrow}|{_escape(edge.label)}| {edge.target}")
        else:
            lines.append(f"    {edge.source} {arrow} {edge.target}")

    for node in spec.nodes:
        if node.emphasis != "normal":
            lines.append(f"    class {node.id} {node.emphasis}")

    if any(n.emphasis != "normal" for n in spec.nodes):
        lines.append("    classDef primary stroke-width:3px")
        lines.append("    classDef muted opacity:0.55")

    return "\n".join(lines) + "\n"
