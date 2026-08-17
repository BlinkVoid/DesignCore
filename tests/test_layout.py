import json
import subprocess

import pytest

from designcore.layout import Placement, layout_groups, layout_spec, to_dot
from designcore.render import BackendMissing
from designcore.spec import DiagramSpec, Edge, Group, Node

SPEC = DiagramSpec(
    id="d", title="T", kind="flow", question="Q?", direction="LR",
    nodes=(Node(id="a", label="A"), Node(id="b", label="Beta")),
    edges=(Edge(source="a", target="b"),),
    groups=(Group(id="g", label="G", members=("a",)),),
)

FAKE_JSON = json.dumps({
    "bb": "0,0,200,100",
    "objects": [
        {"name": "a", "pos": "50,80", "width": "1.0", "height": "0.5"},
        {"name": "b", "pos": "150,80", "width": "1.5", "height": "0.5"},
        {"name": "cluster_g", "bb": "10,10,110,110"},
    ],
})


def _ok(cmd, **kwargs):
    return subprocess.CompletedProcess(cmd, 0, stdout=FAKE_JSON, stderr="")


def test_dot_source_declares_nodes_edges_and_cluster():
    dot = to_dot(SPEC)
    assert "rankdir=LR" in dot
    assert '"a" [label="A"' in dot
    assert '"a" -> "b"' in dot
    assert "subgraph cluster_g" in dot


def test_layout_returns_top_left_pixel_placements():
    placements = layout_spec(SPEC, run=_ok, which=lambda c: "/usr/bin/dot")
    assert set(placements) == {"a", "b"}
    a = placements["a"]
    assert isinstance(a, Placement)
    assert a.width == 72.0            # 1.0 inch at 72 dpi
    assert a.x == 50.0 - 72.0 / 2     # centre-based pos converted to left edge
    assert a.y == 100 - 80 - 36 / 2   # bottom-left origin flipped to top-left


def test_missing_graphviz_raises_backend_missing():
    with pytest.raises(BackendMissing, match="graphviz"):
        layout_spec(SPEC, run=_ok, which=lambda c: None)


def test_clusters_are_not_returned_as_node_placements():
    placements = layout_spec(SPEC, run=_ok, which=lambda c: "/usr/bin/dot")
    assert "cluster_g" not in placements


def test_no_two_nodes_overlap_in_returned_placements():
    placements = layout_spec(SPEC, run=_ok, which=lambda c: "/usr/bin/dot")
    a, b = placements["a"], placements["b"]
    assert a.x + a.width <= b.x or b.x + b.width <= a.x


def test_layout_groups_returns_cluster_bounding_boxes():
    """Amendment A2: group bounding boxes, same top-left pixel convention."""
    groups = layout_groups(SPEC, run=_ok, which=lambda c: "/usr/bin/dot")
    assert set(groups) == {"g"}
    box = groups["g"]
    assert isinstance(box, Placement)
    assert box.x == 10.0              # cluster bb x1
    assert box.width == 110.0 - 10.0  # x2 - x1
    assert box.height == 110.0 - 10.0  # y2 - y1
    assert box.y == 100 - 110.0       # canvas height minus bb top edge


def test_layout_groups_requires_graphviz():
    with pytest.raises(BackendMissing, match="graphviz"):
        layout_groups(SPEC, run=_ok, which=lambda c: None)


def test_quotes_in_labels_are_escaped_for_dot():
    """A label spec.py accepts must not produce a DOT syntax error.

    parse_spec places no charset restriction on labels and the mermaid
    emitter escapes them, so an unescaped quote here means a spec that
    renders as mermaid crashes every layout-dependent format.
    """
    spec = DiagramSpec(
        id="d", title="T", kind="flow", question="Q?", direction="LR",
        nodes=(Node(id="a", label='the "Store"'), Node(id="b", label="B")),
        edges=(Edge(source="a", target="b"),),
        groups=(Group(id="g", label='the "Tier"', members=("a",)),),
    )
    dot = to_dot(spec)
    assert r'label="the \"Store\""' in dot
    assert r'label="the \"Tier\""' in dot


def test_backslashes_in_labels_are_escaped_for_dot():
    spec = DiagramSpec(
        id="d", title="T", kind="flow", question="Q?", direction="LR",
        nodes=(Node(id="a", label=r"C:\path"),),
        edges=(),
    )
    assert r'label="C:\\path"' in to_dot(spec)
