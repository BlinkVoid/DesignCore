import pytest

from designcore.spec import DiagramSpec, SpecError, parse_spec

VALID = {
    "id": "request-flow",
    "title": "Inbound request path",
    "kind": "flow",
    "question": "What happens between an inbound request and a persisted record?",
    "direction": "LR",
    "nodes": [
        {"id": "cdn", "label": "CDN", "role": "infra"},
        {"id": "worker", "label": "API Worker", "role": "service"},
    ],
    "edges": [{"from": "cdn", "to": "worker", "label": "cache miss"}],
    "groups": [{"id": "edge", "label": "Edge", "members": ["cdn", "worker"]}],
}


def test_parses_a_valid_spec():
    spec = parse_spec(VALID)
    assert isinstance(spec, DiagramSpec)
    assert spec.id == "request-flow"
    assert spec.nodes[0].label == "CDN"
    assert spec.edges[0].source == "cdn"
    assert spec.edges[0].target == "worker"
    assert spec.edges[0].kind == "sync"
    assert spec.groups[0].members == ("cdn", "worker")


def test_rejects_missing_question():
    data = {k: v for k, v in VALID.items() if k != "question"}
    with pytest.raises(SpecError, match="question"):
        parse_spec(data)


def test_rejects_edge_pointing_at_undeclared_node():
    data = {**VALID, "edges": [{"from": "cdn", "to": "ghost"}]}
    with pytest.raises(SpecError, match="ghost"):
        parse_spec(data)


def test_rejects_duplicate_node_ids():
    data = {**VALID, "nodes": [{"id": "cdn", "label": "A"}, {"id": "cdn", "label": "B"}]}
    with pytest.raises(SpecError, match="duplicate"):
        parse_spec(data)


def test_rejects_group_member_that_is_not_a_node():
    data = {**VALID, "groups": [{"id": "g", "label": "G", "members": ["ghost"]}]}
    with pytest.raises(SpecError, match="ghost"):
        parse_spec(data)


def test_rejects_node_in_two_groups():
    data = {
        **VALID,
        "groups": [
            {"id": "g1", "label": "One", "members": ["cdn"]},
            {"id": "g2", "label": "Two", "members": ["cdn"]},
        ],
    }
    with pytest.raises(SpecError, match="more than one group"):
        parse_spec(data)


def test_rejects_coordinates_in_the_spec():
    data = {**VALID, "nodes": [{"id": "cdn", "label": "CDN", "x": 10, "y": 20}]}
    with pytest.raises(SpecError, match="coordinates"):
        parse_spec(data)


def test_rejects_unknown_kind():
    with pytest.raises(SpecError, match="kind"):
        parse_spec({**VALID, "kind": "interpretive-dance"})


def test_rejects_an_unknown_direction():
    """direction reaches Mermaid's header and Graphviz's rankdir verbatim, so a
    typo becomes a render-time parse error instead of a spec error."""
    with pytest.raises(SpecError, match="direction"):
        parse_spec({"id": "d", "title": "T", "kind": "flow", "question": "Q?", "direction": "LTR"})


def test_accepts_all_four_directions():
    for direction in ("TB", "BT", "LR", "RL"):
        spec = parse_spec(
            {"id": "d", "title": "T", "kind": "flow", "question": "Q?", "direction": direction}
        )
        assert spec.direction == direction


def test_rejects_a_group_id_colliding_with_a_node_id():
    """Both emitters put groups and nodes in one id namespace: draw.io would
    emit two mxCells with the same id and silently drop one."""
    with pytest.raises(SpecError, match="api"):
        parse_spec({
            "id": "d", "title": "T", "kind": "flow", "question": "Q?",
            "nodes": [{"id": "api", "label": "API"}],
            "groups": [{"id": "api", "label": "API tier", "members": ["api"]}],
        })


def test_rejects_duplicate_group_ids():
    with pytest.raises(SpecError, match="dup"):
        parse_spec({
            "id": "d", "title": "T", "kind": "flow", "question": "Q?",
            "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "groups": [{"id": "dup", "label": "One", "members": ["a"]},
                       {"id": "dup", "label": "Two", "members": ["b"]}],
        })


def test_rejects_a_node_id_in_the_generated_edge_namespace():
    """Edge cells are emitted as edge-0, edge-1, ...; a node named edge-0
    collides with the first edge's id."""
    with pytest.raises(SpecError, match="edge-0"):
        parse_spec({
            "id": "d", "title": "T", "kind": "flow", "question": "Q?",
            "nodes": [{"id": "edge-0", "label": "A"}],
        })
