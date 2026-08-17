"""Checks on graph shape: things that are valid but unreadable."""

from __future__ import annotations

from designcore.lint import Finding
from designcore.spec import DiagramSpec


def check_structure(spec: DiagramSpec) -> list[Finding]:
    findings: list[Finding] = []
    connected = {e.source for e in spec.edges} | {e.target for e in spec.edges}

    for node in spec.nodes:
        if node.id not in connected:
            findings.append(
                Finding(
                    code="ISOLATED_NODE",
                    severity="warning",
                    message=f"node {node.label!r} has no edges; is it part of this diagram?",
                    subject=node.id,
                )
            )

    for edge in spec.edges:
        if edge.source == edge.target:
            findings.append(
                Finding(
                    code="SELF_LOOP",
                    severity="warning",
                    message=f"edge on {edge.source!r} points at itself",
                    subject=edge.source,
                )
            )

    for group in spec.groups:
        if not group.members:
            findings.append(
                Finding(
                    code="EMPTY_GROUP",
                    severity="warning",
                    message=f"group {group.label or group.id!r} contains no nodes",
                    subject=group.id,
                )
            )

    return findings
