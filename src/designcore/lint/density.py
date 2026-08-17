"""Density checks: a diagram that answers one question stays small."""

from __future__ import annotations

from designcore.lint import Finding
from designcore.spec import DiagramSpec

THRESHOLDS: dict[str, int] = {
    "context": 12,
    "container": 16,
    "deployment": 16,
    "network": 20,
    "sequence": 10,
    "state": 14,
    "flow": 18,
    "concept": 12,
}
DEFAULT_THRESHOLD = 16


def check_density(spec: DiagramSpec) -> list[Finding]:
    limit = THRESHOLDS.get(spec.kind, DEFAULT_THRESHOLD)
    if len(spec.nodes) <= limit:
        return []
    return [
        Finding(
            code="TOO_DENSE",
            severity="error",
            message=(
                f"{len(spec.nodes)} nodes exceeds the {limit}-node limit for kind {spec.kind!r}; "
                "split this into diagrams that each answer one question"
            ),
            subject=spec.id,
        )
    ]
