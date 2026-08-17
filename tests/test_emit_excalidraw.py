import pytest

from designcore.emit.excalidraw import emit_excalidraw
from designcore.layout import Placement
from designcore.spec import DiagramSpec, Edge, Node

SPEC = DiagramSpec(
    id="d", title="T", kind="concept", question="Q?",
    nodes=(Node(id="a", label="Alpha"), Node(id="b", label="Beta", emphasis="primary")),
    edges=(Edge(source="a", target="b", label="calls"),),
)
PLACEMENTS = {
    "a": Placement("a", 0, 0, 100, 50),
    "b": Placement("b", 200, 0, 100, 50),
}


def test_emits_a_valid_excalidraw_document():
    doc = emit_excalidraw(SPEC, PLACEMENTS)
    assert doc["type"] == "excalidraw"
    assert doc["version"] == 2
    assert doc["source"] == "designcore"
    assert isinstance(doc["elements"], list)


def test_each_node_becomes_a_rectangle_at_its_placement():
    elements = emit_excalidraw(SPEC, PLACEMENTS)["elements"]
    rects = [e for e in elements if e["type"] == "rectangle"]
    assert len(rects) == 2
    first = next(r for r in rects if r["x"] == 0)
    assert (first["y"], first["width"], first["height"]) == (0, 100, 50)


def test_each_node_gets_a_bound_text_label():
    elements = emit_excalidraw(SPEC, PLACEMENTS)["elements"]
    texts = [e for e in elements if e["type"] == "text"]
    assert {t["text"] for t in texts} >= {"Alpha", "Beta"}


def test_each_edge_becomes_an_arrow_between_the_right_elements():
    elements = emit_excalidraw(SPEC, PLACEMENTS)["elements"]
    arrows = [e for e in elements if e["type"] == "arrow"]
    assert len(arrows) == 1
    assert arrows[0]["startBinding"]["elementId"] == "a"
    assert arrows[0]["endBinding"]["elementId"] == "b"


def test_primary_emphasis_gets_a_thicker_stroke():
    elements = emit_excalidraw(SPEC, PLACEMENTS)["elements"]
    b = next(e for e in elements if e.get("id") == "b")
    a = next(e for e in elements if e.get("id") == "a")
    assert b["strokeWidth"] > a["strokeWidth"]


def test_missing_placement_is_an_error_not_a_guess():
    with pytest.raises(KeyError):
        emit_excalidraw(SPEC, {"a": PLACEMENTS["a"]})
