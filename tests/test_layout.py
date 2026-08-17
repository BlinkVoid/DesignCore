import json
import subprocess

import pytest

from designcore.layout import Placement, layout_all, layout_groups, layout_spec, to_dot
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


def test_edge_labels_reach_the_dot_source():
    """Graphviz reserves rank separation for labelled edges, but only if the
    label is declared. Omitting it lays nodes out too close together, and a
    downstream renderer's opaque label then covers the whole arrow.
    """
    spec = DiagramSpec(
        id="d", title="T", kind="flow", question="Q?", direction="LR",
        nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
        edges=(Edge(source="a", target="b", label="source file"),),
    )
    assert '"a" -> "b" [label="source file"]' in to_dot(spec)


def test_labelled_edges_get_more_separation_than_unlabelled_ones():
    def _spec(label: str):
        return DiagramSpec(
            id="d", title="T", kind="flow", question="Q?", direction="LR",
            nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
            edges=(Edge(source="a", target="b", label=label),),
        )

    def _gap(spec):
        p = layout_spec(spec)
        return p["b"].x - (p["a"].x + p["a"].width)

    assert _gap(_spec("a long edge label")) > _gap(_spec(""))


def test_all_four_directions_reach_rankdir_unfolded():
    """RL and BT must not collapse to LR/TB: Mermaid honours them, so folding
    them here makes one spec lay out differently per format."""
    for direction in ("TB", "BT", "LR", "RL"):
        spec = DiagramSpec(
            id="d", title="T", kind="flow", question="Q?", direction=direction,
            nodes=(Node(id="a", label="A"),), edges=(),
        )
        assert f"rankdir={direction};" in to_dot(spec)


def test_placements_and_group_boxes_come_from_one_dot_run():
    """Two independent dot invocations double the layout cost of every drawio
    render and would silently desynchronise if layout ever stopped being
    deterministic."""
    calls: list = []

    def counting_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=FAKE_JSON, stderr="")

    nodes, groups = layout_all(SPEC, run=counting_run, which=lambda c: "/usr/bin/dot")
    assert len(calls) == 1
    assert set(nodes) == {"a", "b"}
    assert set(groups) == {"g"}
