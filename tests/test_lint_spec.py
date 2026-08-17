from designcore.lint import Finding
from designcore.lint.density import THRESHOLDS, check_density
from designcore.lint.structural import check_structure
from designcore.spec import DiagramSpec, Edge, Group, Node


def _spec(**overrides) -> DiagramSpec:
    base = dict(
        id="d", title="T", kind="flow", question="Q?",
        nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
        edges=(Edge(source="a", target="b"),),
        groups=(),
    )
    return DiagramSpec(**{**base, "direction": "TB", **overrides})


def test_clean_spec_has_no_structural_findings():
    assert check_structure(_spec()) == []


def test_flags_isolated_node():
    spec = _spec(nodes=(Node(id="a", label="A"), Node(id="b", label="B"), Node(id="c", label="C")))
    findings = check_structure(spec)
    assert [f.code for f in findings] == ["ISOLATED_NODE"]
    assert findings[0].subject == "c"
    assert findings[0].severity == "warning"


def test_flags_empty_group():
    spec = _spec(groups=(Group(id="g", label="G", members=()),))
    assert [f.code for f in check_structure(spec)] == ["EMPTY_GROUP"]


def test_flags_self_loop():
    spec = _spec(edges=(Edge(source="a", target="a"),))
    codes = {f.code for f in check_structure(spec)}
    assert "SELF_LOOP" in codes


def test_density_under_threshold_is_clean():
    assert check_density(_spec()) == []


def test_density_over_threshold_says_split():
    nodes = tuple(Node(id=f"n{i}", label=f"N{i}") for i in range(THRESHOLDS["flow"] + 1))
    edges = tuple(Edge(source="n0", target=f"n{i}") for i in range(1, len(nodes)))
    finding = check_density(_spec(nodes=nodes, edges=edges))[0]
    assert finding.code == "TOO_DENSE"
    assert finding.severity == "error"
    assert "split" in finding.message.lower()


def test_findings_are_comparable():
    a = Finding(code="X", severity="warning", message="m", subject="s")
    assert a == Finding(code="X", severity="warning", message="m", subject="s")
