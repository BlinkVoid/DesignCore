import pytest

from designcore.emit.excalidraw import emit_excalidraw
from designcore.layout import Placement
from designcore.spec import DiagramSpec, Edge, Group, Node

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


def test_stacked_boxes_connect_vertically_even_when_centres_are_offset():
    """Real TB layout from FigmentLab: the boxes overlap horizontally and are
    cleanly separated vertically, but their centres are further apart on x.
    Choosing the axis by centre distance sent the arrow out of the right edge
    and backwards across the diagram."""
    arrow = _arrow(
        "TB",
        {"a": Placement("a", 0, 0, 297, 36), "b": Placement("b", 204.5, 87, 172, 36)},
    )
    assert arrow["x"] == 148.5          # centre of a, not its right edge
    assert arrow["y"] == 36             # bottom edge of a
    assert arrow["height"] == 51        # down to the top edge of b
    assert arrow["width"] == 142.0      # lateral drift only, never negative-backwards


def test_separated_axis_wins_over_larger_centre_delta():
    """Boxes side by side but vertically overlapping must connect horizontally
    even if the vertical centre delta happens to be larger."""
    arrow = _arrow(
        "LR",
        {"a": Placement("a", 0, 0, 40, 200), "b": Placement("b", 90, 150, 40, 200)},
    )
    assert arrow["x"] == 40             # right edge of a
    assert arrow["width"] == 50         # to left edge of b


def _rects(spec, placements):
    return [e for e in emit_excalidraw(spec, placements)["elements"] if e["type"] == "rectangle"]


def _role_spec(*roles):
    nodes = tuple(Node(id=f"n{i}", label=f"N{i}", role=r) for i, r in enumerate(roles))
    placements = {n.id: Placement(n.id, i * 200, 0, 100, 50) for i, n in enumerate(nodes)}
    spec = DiagramSpec(
        id="d", title="T", kind="concept", question="Q?", direction="LR",
        nodes=nodes, edges=(),
    )
    return spec, placements


def test_every_shape_gets_its_own_seed():
    """rough.js derives the hand-drawn wobble from the seed, so one shared
    seed makes every box wobble identically -- which reads as mechanical."""
    spec, placements = _role_spec("service", "service", "service", "service")
    seeds = [r["seed"] for r in _rects(spec, placements)]
    assert len(set(seeds)) == len(seeds)


def test_seeds_are_stable_across_runs():
    spec, placements = _role_spec("service", "store")
    assert [r["seed"] for r in _rects(spec, placements)] == [
        r["seed"] for r in _rects(spec, placements)
    ]


def test_rectangles_are_rounded_like_excalidraw_draws_them():
    spec, placements = _role_spec("service")
    assert _rects(spec, placements)[0]["roundness"] == {"type": 3}


def test_roles_get_distinct_colours():
    spec, placements = _role_spec("service", "store", "actor", "note")
    rects = _rects(spec, placements)
    assert len({r["backgroundColor"] for r in rects}) > 1
    assert all(r["backgroundColor"] != "transparent" for r in rects)


def test_filled_shapes_use_the_hachure_style():
    spec, placements = _role_spec("service")
    assert _rects(spec, placements)[0]["fillStyle"] == "hachure"


def test_external_role_is_drawn_dashed_and_unfilled():
    spec, placements = _role_spec("external")
    rect = _rects(spec, placements)[0]
    assert rect["strokeStyle"] == "dashed"
    assert rect["backgroundColor"] == "transparent"


def test_arrow_follows_the_graphviz_route_when_one_is_given():
    """A straight point-to-point arrow cuts through whatever sits between the
    endpoints; Graphviz already routed a path around it."""
    spec = DiagramSpec(
        id="d", title="T", kind="concept", question="Q?", direction="TB",
        nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
        edges=(Edge(source="a", target="b"),),
    )
    placements = {"a": Placement("a", 0, 0, 60, 30), "b": Placement("b", 0, 120, 60, 30)}
    routes = {("a", "b"): ((30.0, 30.0), (80.0, 60.0), (80.0, 90.0), (30.0, 120.0))}
    arrow = next(
        e for e in emit_excalidraw(spec, placements, routes)["elements"] if e["type"] == "arrow"
    )
    assert arrow["x"] == 30.0 and arrow["y"] == 30.0
    assert arrow["points"] == [[0.0, 0.0], [50.0, 30.0], [50.0, 60.0], [0.0, 90.0]]
    assert arrow["roundness"] == {"type": 2}   # smooth the routed path


def test_arrow_falls_back_to_straight_when_no_route_exists():
    arrow = _arrow("LR", {"a": Placement("a", 0, 0, 100, 50), "b": Placement("b", 200, 0, 100, 50)})
    assert arrow["points"] == [[0, 0], [100, 0]]


def test_routed_arrow_still_binds_to_its_endpoints():
    spec = DiagramSpec(
        id="d", title="T", kind="concept", question="Q?", direction="TB",
        nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
        edges=(Edge(source="a", target="b"),),
    )
    placements = {"a": Placement("a", 0, 0, 60, 30), "b": Placement("b", 0, 120, 60, 30)}
    routes = {("a", "b"): ((30.0, 30.0), (30.0, 120.0))}
    arrow = next(
        e for e in emit_excalidraw(spec, placements, routes)["elements"] if e["type"] == "arrow"
    )
    assert arrow["startBinding"]["elementId"] == "a"
    assert arrow["endBinding"]["elementId"] == "b"


def _grouped():
    spec = DiagramSpec(
        id="d", title="T", kind="container", question="Q?", direction="TB",
        nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
        edges=(Edge(source="a", target="b"),),
        groups=(Group(id="tier", label="Data tier", members=("a",)),),
    )
    placements = {"a": Placement("a", 20, 20, 60, 30), "b": Placement("b", 20, 150, 60, 30)}
    groups = {"tier": Placement("tier", 10, 10, 90, 60)}
    return spec, placements, groups


def test_groups_become_labelled_boxes():
    """mermaid draws subgraphs and drawio draws container cells; dropping them
    here loses a boundary the spec explicitly declared."""
    spec, placements, groups = _grouped()
    elements = emit_excalidraw(spec, placements, None, groups)["elements"]
    box = next(e for e in elements if e.get("id") == "tier")
    assert (box["x"], box["y"], box["width"], box["height"]) == (10, 10, 90, 60)
    assert box["strokeStyle"] == "dashed"
    assert box["backgroundColor"] == "transparent"
    assert any(e.get("text") == "Data tier" for e in elements)


def test_group_boxes_are_emitted_before_their_members():
    """Excalidraw paints in array order, so a container declared after its
    members would cover them."""
    spec, placements, groups = _grouped()
    ids = [e.get("id") for e in emit_excalidraw(spec, placements, None, groups)["elements"]]
    assert ids.index("tier") < ids.index("a")


def test_groups_are_optional():
    spec, placements, _ = _grouped()
    assert emit_excalidraw(spec, placements)["elements"]
