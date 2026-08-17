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


def _arrow(direction: str, placements: dict) -> dict:
    spec = DiagramSpec(
        id="d", title="T", kind="concept", question="Q?", direction=direction,
        nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
        edges=(Edge(source="a", target="b"),),
    )
    return next(e for e in emit_excalidraw(spec, placements)["elements"] if e["type"] == "arrow")


def test_vertical_layout_arrow_runs_downward_not_backwards():
    """TB is the spec default and what `designcore new` scaffolds, and
    excalidraw is the default format for kind: concept -- so a hardcoded
    left-to-right exit point breaks the default path for this emitter.
    """
    arrow = _arrow("TB", {"a": Placement("a", 0, 0, 54, 36), "b": Placement("b", 0, 72, 54, 36)})
    assert arrow["width"] == 0          # straight down, not diagonally backwards
    assert arrow["height"] > 0
    assert arrow["y"] == 36             # leaves the bottom edge of a
    assert arrow["points"][-1] == [0, 36]  # to the top edge of b


def test_horizontal_layout_arrow_still_runs_rightward():
    arrow = _arrow("LR", {"a": Placement("a", 0, 0, 100, 50), "b": Placement("b", 200, 0, 100, 50)})
    assert arrow["x"] == 100            # leaves the right edge of a
    assert arrow["width"] == 100        # to the left edge of b
    assert arrow["height"] == 0


def test_upward_layout_arrow_runs_upward():
    arrow = _arrow("BT", {"a": Placement("a", 0, 72, 54, 36), "b": Placement("b", 0, 0, 54, 36)})
    assert arrow["y"] == 72             # leaves the top edge of a
    assert arrow["points"][-1] == [0, -36]


def test_edge_label_box_grows_with_the_text():
    """exportToSvg derives the scene bounding box from declared width/height,
    so a label wider than its box overflows and can be cropped."""
    def _label_width(text: str) -> float:
        spec = DiagramSpec(
            id="d", title="T", kind="concept", question="Q?", direction="LR",
            nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
            edges=(Edge(source="a", target="b", label=text),),
        )
        elements = emit_excalidraw(spec, PLACEMENTS)["elements"]
        return next(e for e in elements if e.get("id") == "edge-0-label")["width"]

    assert _label_width("a much longer edge label") > _label_width("hi")
    assert _label_width("a much longer edge label") >= 24 * 12 * 0.5
