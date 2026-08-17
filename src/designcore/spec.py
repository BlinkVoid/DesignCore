"""The graph spec: what a diagram contains, never where anything sits."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

KINDS = frozenset(
    {"context", "container", "deployment", "network", "sequence", "state", "flow", "concept"}
)
ROLES = frozenset({"actor", "service", "store", "infra", "external", "note"})
EMPHASES = frozenset({"normal", "primary", "muted"})
EDGE_KINDS = frozenset({"sync", "async", "data", "dashed"})
# Reaches Mermaid's `flowchart <direction>` header and Graphviz's rankdir
# verbatim, so an unvalidated typo surfaces as a render-time parse failure
# rather than a SpecError here.
DIRECTIONS = frozenset({"TB", "BT", "LR", "RL"})
# Emitters name edge cells `edge-<index>`, so those ids are not the author's
# to use.
RESERVED_ID_PREFIX_RE = re.compile(r"^edge-\d+$")
GEOMETRY_KEYS = frozenset({"x", "y", "width", "height", "position"})


class SpecError(ValueError):
    """A spec that cannot be compiled into a diagram."""


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    role: str = "service"
    emphasis: str = "normal"


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str = ""
    kind: str = "sync"


@dataclass(frozen=True)
class Group:
    id: str
    label: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class DiagramSpec:
    id: str
    title: str
    kind: str
    question: str
    direction: str = "TB"
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    groups: tuple[Group, ...] = ()


def _require(data: dict, field: str) -> str:
    value = data.get(field)
    if not value or not str(value).strip():
        raise SpecError(f"spec is missing required field {field!r}")
    return str(value)


def _one_of(value: str, allowed: frozenset[str], field: str) -> str:
    if value not in allowed:
        raise SpecError(f"unknown {field} {value!r}; expected one of {sorted(allowed)}")
    return value


def parse_spec(data: dict) -> DiagramSpec:
    """Build a validated DiagramSpec from raw mapping data."""
    spec_id = _require(data, "id")
    title = _require(data, "title")
    kind = _one_of(_require(data, "kind"), KINDS, "kind")
    question = _require(data, "question")

    nodes: list[Node] = []
    seen: set[str] = set()
    for raw in data.get("nodes", []):
        leaked = GEOMETRY_KEYS & set(raw)
        if leaked:
            raise SpecError(
                f"node {raw.get('id')!r} declares coordinates {sorted(leaked)}; "
                "geometry comes from the layout engine, never from the spec"
            )
        node_id = _require(raw, "id")
        if node_id in seen:
            raise SpecError(f"duplicate node id {node_id!r}")
        if RESERVED_ID_PREFIX_RE.match(node_id):
            raise SpecError(
                f"node id {node_id!r} collides with the generated edge id namespace; "
                "ids matching 'edge-<number>' are reserved for emitted edge cells"
            )
        seen.add(node_id)
        nodes.append(
            Node(
                id=node_id,
                label=str(raw.get("label", node_id)),
                role=_one_of(str(raw.get("role", "service")), ROLES, "role"),
                emphasis=_one_of(str(raw.get("emphasis", "normal")), EMPHASES, "emphasis"),
            )
        )

    edges: list[Edge] = []
    for raw in data.get("edges", []):
        source, target = _require(raw, "from"), _require(raw, "to")
        for endpoint in (source, target):
            if endpoint not in seen:
                raise SpecError(f"edge endpoint {endpoint!r} is not a declared node")
        edges.append(
            Edge(
                source=source,
                target=target,
                label=str(raw.get("label", "")),
                kind=_one_of(str(raw.get("kind", "sync")), EDGE_KINDS, "edge kind"),
            )
        )

    groups: list[Group] = []
    claimed: set[str] = set()
    group_ids: set[str] = set()
    for raw in data.get("groups", []):
        # Groups and nodes share one id namespace in both emitters: mxGraph
        # cells and Mermaid subgraphs are keyed by the same ids, so a
        # collision means one of the two is silently dropped at render time.
        group_id = _require(raw, "id")
        if group_id in seen:
            raise SpecError(f"group id {group_id!r} is already used by a node")
        if group_id in group_ids:
            raise SpecError(f"duplicate group id {group_id!r}")
        group_ids.add(group_id)
        members = tuple(str(m) for m in raw.get("members", []))
        for member in members:
            if member not in seen:
                raise SpecError(f"group member {member!r} is not a declared node")
            if member in claimed:
                raise SpecError(f"node {member!r} belongs to more than one group")
            claimed.add(member)
        groups.append(Group(id=group_id, label=str(raw.get("label", "")), members=members))

    return DiagramSpec(
        id=spec_id,
        title=title,
        kind=kind,
        question=question,
        direction=_one_of(str(data.get("direction", "TB")).upper(), DIRECTIONS, "direction"),
        nodes=tuple(nodes),
        edges=tuple(edges),
        groups=tuple(groups),
    )


def load_spec(path: Path) -> DiagramSpec:
    """Read and validate a .spec.yaml file."""
    with Path(path).open(encoding="utf-8") as handle:
        return parse_spec(yaml.safe_load(handle) or {})
