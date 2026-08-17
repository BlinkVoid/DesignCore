from xml.etree import ElementTree

import pytest

from designcore.emit.drawio import emit_drawio
from designcore.layout import Placement
from designcore.spec import DiagramSpec, Edge, Group, Node

SPEC = DiagramSpec(
    id="d", title="T", kind="container", question="Q?",
    nodes=(Node(id="a", label="Alpha", role="store"),
           Node(id="b", label="Beta", emphasis="primary")),
    edges=(Edge(source="a", target="b", label="calls"),),
)
PLACEMENTS = {
    "a": Placement("a", 0, 0, 120, 60),
    "b": Placement("b", 200, 10, 120, 60),
}


def _cells(xml: str) -> dict[str, ElementTree.Element]:
    root = ElementTree.fromstring(xml)
    return {c.get("id"): c for c in root.iter("mxCell")}


def test_returns_parseable_mxfile_xml():
    assert ElementTree.fromstring(emit_drawio(SPEC, PLACEMENTS)).tag == "mxfile"


def test_declares_the_two_mxgraph_root_cells():
    cells = _cells(emit_drawio(SPEC, PLACEMENTS))
    assert "0" in cells
    assert cells["1"].get("parent") == "0"


def test_each_node_becomes_a_vertex_with_its_placement_geometry():
    cells = _cells(emit_drawio(SPEC, PLACEMENTS))
    assert cells["b"].get("vertex") == "1"
    geometry = cells["b"].find("mxGeometry")
    assert geometry.get("x") == "200"
    assert geometry.get("y") == "10"
    assert geometry.get("width") == "120"
    assert geometry.get("height") == "60"


def test_node_label_becomes_the_cell_value():
    assert _cells(emit_drawio(SPEC, PLACEMENTS))["a"].get("value") == "Alpha"


def test_emphasis_and_role_reach_the_style_string():
    cells = _cells(emit_drawio(SPEC, PLACEMENTS))
    assert "strokeWidth=3" in cells["b"].get("style")
    assert "strokeWidth=3" not in cells["a"].get("style")
    assert "cylinder3" in cells["a"].get("style")  # role=store


def test_each_edge_becomes_an_orthogonal_edge_cell():
    cells = _cells(emit_drawio(SPEC, PLACEMENTS))
    edge = next(c for c in cells.values() if c.get("edge") == "1")
    assert edge.get("source") == "a"
    assert edge.get("target") == "b"
    assert edge.get("value") == "calls"
    assert "orthogonalEdgeStyle" in edge.get("style")


def test_groups_become_container_cells_with_their_own_bounds():
    spec = DiagramSpec(
        id="d", title="T", kind="container", question="Q?",
        nodes=SPEC.nodes, edges=SPEC.edges,
        groups=(Group(id="g", label="Tier", members=("a",)),),
    )
    xml = emit_drawio(spec, PLACEMENTS, {"g": Placement("g", -8, -8, 150, 80)})
    cells = _cells(xml)
    assert cells["g"].get("value") == "Tier"
    assert cells["g"].find("mxGeometry").get("width") == "150"


def test_group_cells_precede_node_cells_so_they_render_behind():
    spec = DiagramSpec(
        id="d", title="T", kind="container", question="Q?",
        nodes=SPEC.nodes, edges=SPEC.edges,
        groups=(Group(id="g", label="Tier", members=("a",)),),
    )
    xml = emit_drawio(spec, PLACEMENTS, {"g": Placement("g", -8, -8, 150, 80)})
    order = [c.get("id") for c in ElementTree.fromstring(xml).iter("mxCell")]
    assert order.index("g") < order.index("a")


def test_xml_special_characters_in_labels_are_escaped():
    """Amendment A8's carry-forward: mxGraph values need &, <, > escaped."""
    spec = DiagramSpec(
        id="d", title="T", kind="container", question="Q?",
        nodes=(Node(id="a", label='A & B <fast> "x"'),), edges=(),
    )
    xml = emit_drawio(spec, {"a": Placement("a", 0, 0, 10, 10)})
    assert "&amp;" in xml
    assert "<fast>" not in xml


def test_labels_are_html_escaped_because_cells_declare_html_1():
    """Cells carry html=1, so draw.io parses the value as HTML.

    XML escaping alone is not enough: a real render showed '<fast>' silently
    swallowed as an unknown HTML tag while the XML itself was well formed.
    The stored value must therefore be the HTML-escaped text.
    """
    spec = DiagramSpec(
        id="d", title="T", kind="container", question="Q?",
        nodes=(Node(id="a", label="A & B <fast>"),), edges=(),
    )
    xml = emit_drawio(spec, {"a": Placement("a", 0, 0, 10, 10)})
    assert "html=1" in _cells(xml)["a"].get("style")
    assert _cells(xml)["a"].get("value") == "A &amp; B &lt;fast&gt;"


def test_edge_labels_are_html_escaped_too():
    spec = DiagramSpec(
        id="d", title="T", kind="container", question="Q?",
        nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
        edges=(Edge(source="a", target="b", label="a < b & c"),),
    )
    xml = emit_drawio(spec, {"a": Placement("a", 0, 0, 10, 10), "b": Placement("b", 50, 0, 10, 10)})
    edge = next(c for c in _cells(xml).values() if c.get("edge") == "1")
    assert edge.get("value") == "a &lt; b &amp; c"


def test_missing_placement_is_an_error_not_a_guess():
    with pytest.raises(KeyError):
        emit_drawio(SPEC, {"a": PLACEMENTS["a"]})


def test_group_cells_declare_html_so_their_labels_are_not_double_escaped():
    """Group labels go through the same HTML escaping as nodes and edges, so
    the group style must also declare html=1 or draw.io shows the entities
    literally ('Prod &amp; Staging')."""
    spec = DiagramSpec(
        id="d", title="T", kind="container", question="Q?",
        nodes=(Node(id="a", label="A"),), edges=(),
        groups=(Group(id="g", label="Prod & Staging", members=("a",)),),
    )
    xml = emit_drawio(spec, {"a": Placement("a", 0, 0, 10, 10)}, {"g": Placement("g", 0, 0, 50, 50)})
    cells = _cells(xml)
    assert "html=1" in cells["g"].get("style")
    assert cells["g"].get("value") == "Prod &amp; Staging"
