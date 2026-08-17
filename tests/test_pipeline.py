from pathlib import Path

import pytest

from designcore.layout import Placement
from designcore.pipeline import Deps, compile_diagram, lint_diagram
from designcore.render import BackendMissing
from designcore.spec import DiagramSpec, Edge, Node

SPEC = DiagramSpec(
    id="request-flow", title="Request flow", kind="flow", question="What happens on request?",
    direction="LR",
    nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
    edges=(Edge(source="a", target="b"),),
)


def _deps(tmp_path: Path) -> Deps:
    def fake_render(source: Path, out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        svg = out_dir / (source.stem + ".svg")
        png = out_dir / (source.stem + ".png")
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"/>', encoding="utf-8")
        png.write_bytes(b"png")
        return [svg, png]

    return Deps(
        render_map={"mermaid": fake_render, "drawio": fake_render, "excalidraw": fake_render},
        layout=lambda spec: {
            "a": Placement("a", 0, 0, 100, 50),
            "b": Placement("b", 200, 0, 100, 50),
        },
        layout_groups=lambda spec: {},
    )


def test_compile_writes_source_and_renders_for_mermaid(tmp_path):
    entry = compile_diagram(SPEC, "mermaid", tmp_path, _deps(tmp_path))
    assert (tmp_path / entry.source).exists()
    assert (tmp_path / entry.source).suffix == ".mmd"
    assert all((tmp_path / r).exists() for r in entry.rendered)
    assert entry.question == SPEC.question


def test_compile_writes_drawio_xml(tmp_path):
    entry = compile_diagram(SPEC, "drawio", tmp_path, _deps(tmp_path))
    assert (tmp_path / entry.source).suffix == ".drawio"
    assert (tmp_path / entry.source).read_text(encoding="utf-8").startswith("<mxfile")


def test_compile_writes_excalidraw_json(tmp_path):
    import json

    entry = compile_diagram(SPEC, "excalidraw", tmp_path, _deps(tmp_path))
    doc = json.loads((tmp_path / entry.source).read_text(encoding="utf-8"))
    assert doc["type"] == "excalidraw"


def test_compile_refuses_to_overwrite_a_hand_owned_source(tmp_path):
    deps = _deps(tmp_path)
    compile_diagram(SPEC, "mermaid", tmp_path, deps)
    with pytest.raises(PermissionError, match="hand_owned"):
        compile_diagram(SPEC, "mermaid", tmp_path, deps, hand_owned=True)


def test_compile_propagates_backend_missing(tmp_path):
    def missing(source, out_dir):
        raise BackendMissing("mmdc is not installed")

    deps = Deps(render_map={"mermaid": missing}, layout=lambda s: {}, layout_groups=lambda s: {})
    with pytest.raises(BackendMissing):
        compile_diagram(SPEC, "mermaid", tmp_path, deps)


def test_lint_diagram_combines_all_three_check_families(tmp_path):
    svg = tmp_path / "d.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"/>', encoding="utf-8")
    placements = {"a": Placement("a", 0, 0, 100, 50), "b": Placement("b", 50, 0, 100, 50)}
    codes = {f.code for f in lint_diagram(SPEC, placements, svg)}
    assert "NODE_OVERLAP" in codes


def test_formats_render_into_separate_directories(tmp_path):
    """Two formats of one diagram must not overwrite each other's renders.

    Renderers name their output from the source stem, which is the diagram id
    for every format, so a shared out/ directory silently clobbers.
    """
    deps = _deps(tmp_path)
    mermaid = compile_diagram(SPEC, "mermaid", tmp_path, deps)
    drawio = compile_diagram(SPEC, "drawio", tmp_path, deps)

    assert set(mermaid.rendered).isdisjoint(drawio.rendered)
    assert all((tmp_path / r).exists() for r in mermaid.rendered)
    assert all((tmp_path / r).exists() for r in drawio.rendered)


def test_lint_skips_placement_geometry_when_the_format_does_not_use_it():
    """Mermaid computes its own layout, so linting Graphviz placements reports
    on geometry no output file uses. Passing none is the honest signal."""
    from designcore.pipeline import GEOMETRY_FORMATS

    assert "mermaid" not in GEOMETRY_FORMATS
    assert {"drawio", "excalidraw"} <= GEOMETRY_FORMATS


def test_lint_includes_group_boxes_in_the_overlap_check():
    """Group boxes are emitted geometry too; overlapping containers are just
    as unreadable as overlapping nodes."""
    overlapping = {
        "a": Placement("a", 0, 0, 100, 50),
        "g": Placement("g", 10, 10, 100, 50),
    }
    codes = {f.code for f in lint_diagram(SPEC, overlapping, None)}
    assert "NODE_OVERLAP" in codes
