from designcore.emit.mermaid import emit_mermaid
from designcore.spec import DiagramSpec, Edge, Group, Node


def _spec(**overrides) -> DiagramSpec:
    base = dict(
        id="d", title="T", kind="flow", question="Q?", direction="LR",
        nodes=(Node(id="cdn", label="CDN", role="infra"),
               Node(id="worker", label="API Worker", role="service", emphasis="primary")),
        edges=(Edge(source="cdn", target="worker", label="cache miss"),),
        groups=(),
    )
    return DiagramSpec(**{**base, **overrides})


def test_emits_flowchart_header_with_direction():
    assert emit_mermaid(_spec()).splitlines()[0] == "flowchart LR"


def test_emits_nodes_and_labelled_edge():
    out = emit_mermaid(_spec())
    assert 'cdn["CDN"]' in out
    assert 'worker["API Worker"]' in out
    assert "cdn -->|cache miss| worker" in out


def test_unlabelled_edge_has_no_pipe_section():
    out = emit_mermaid(_spec(edges=(Edge(source="cdn", target="worker"),)))
    assert "cdn --> worker" in out
    assert "|" not in out


def test_async_edge_uses_dotted_arrow():
    out = emit_mermaid(_spec(edges=(Edge(source="cdn", target="worker", kind="async"),)))
    assert "cdn -.-> worker" in out


def test_groups_become_subgraphs():
    out = emit_mermaid(_spec(groups=(Group(id="edge", label="Edge", members=("cdn",)),)))
    assert 'subgraph edge["Edge"]' in out
    assert out.count("end") == 1


def test_emphasis_becomes_a_class_directive():
    out = emit_mermaid(_spec())
    assert "class worker primary" in out


def test_quotes_in_labels_are_escaped():
    out = emit_mermaid(_spec(nodes=(Node(id="a", label='the "edge"'),
                                    Node(id="worker", label="W"))))
    assert '&quot;edge&quot;' in out
    assert '"the "edge""' not in out


def test_output_is_deterministic():
    assert emit_mermaid(_spec()) == emit_mermaid(_spec())
