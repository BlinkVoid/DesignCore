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
