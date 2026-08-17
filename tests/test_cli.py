from pathlib import Path

import pytest
import yaml

from designcore.cli import main


def test_new_scaffolds_a_spec_with_the_question_prompt(tmp_path, capsys):
    code = main(["new", "request-flow", "--kind", "flow", "--root", str(tmp_path)])
    assert code == 0
    spec_file = tmp_path / "src" / "request-flow.spec.yaml"
    data = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
    assert data["kind"] == "flow"
    assert "question" in data
    assert data["nodes"] == []


def test_check_reports_findings_and_exit_code(tmp_path):
    (tmp_path / "diagrams.yaml").write_text(
        yaml.safe_dump({
            "version": 1,
            "diagrams": [{
                "id": "d", "title": "T", "kind": "flow", "format": "mermaid",
                "question": "Q?", "spec": "src/d.spec.yaml", "source": "src/d.mmd",
                "rendered": [], "embedded_in": [],
            }],
        }),
        encoding="utf-8",
    )
    assert main(["check", "--root", str(tmp_path)]) == 1


def test_lint_on_a_clean_spec_exits_zero(tmp_path):
    spec = tmp_path / "src" / "d.spec.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        yaml.safe_dump({
            "id": "d", "title": "T", "kind": "flow", "question": "Q?",
            "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "edges": [{"from": "a", "to": "b"}],
        }),
        encoding="utf-8",
    )
    assert main(["lint", "d", "--root", str(tmp_path)]) == 0


def test_unknown_command_is_rejected(capsys):
    try:
        main(["frobnicate"])
    except SystemExit as exc:
        assert exc.code != 0


def test_lint_finds_the_render_in_its_format_directory(tmp_path):
    """Renders live in out/<format>/; looking in out/ skips check_svg_bounds
    entirely and reports a clipped diagram as clean."""
    spec = tmp_path / "src" / "d.spec.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        yaml.safe_dump({
            "id": "d", "title": "T", "kind": "flow", "question": "Q?",
            "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "edges": [{"from": "a", "to": "b"}],
        }),
        encoding="utf-8",
    )
    rendered = tmp_path / "out" / "mermaid" / "d.svg"
    rendered.parent.mkdir(parents=True)
    rendered.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect x="10" y="10" width="500" height="50"/></svg>',
        encoding="utf-8",
    )
    assert main(["lint", "d", "--root", str(tmp_path)]) == 1


def test_check_without_a_manifest_reports_instead_of_traceback(tmp_path, capsys):
    """Backend and spec errors carry carefully worded install/fix hints; letting
    them escape main turns each one into a traceback."""
    assert main(["check", "--root", str(tmp_path)]) == 1
    assert "diagrams.yaml" in capsys.readouterr().out


def test_backend_missing_is_reported_with_its_install_hint(tmp_path, capsys, monkeypatch):
    import designcore.cli as cli
    from designcore.render import BackendMissing

    spec = tmp_path / "src" / "d.spec.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        yaml.safe_dump({"id": "d", "title": "T", "kind": "flow", "question": "Q?",
                        "nodes": [{"id": "a", "label": "A"}], "edges": []}),
        encoding="utf-8",
    )

    def boom(*args, **kwargs):
        raise BackendMissing("dot is not installed. Install it with: apt install graphviz")

    monkeypatch.setattr(cli, "compile_diagram", boom)
    assert main(["render", "d", "--root", str(tmp_path)]) == 1
    assert "apt install graphviz" in capsys.readouterr().out


def test_malformed_spec_is_reported_not_raised(tmp_path, capsys):
    spec = tmp_path / "src" / "d.spec.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text(yaml.safe_dump({"id": "d", "title": "T", "kind": "nonsense",
                                    "question": "Q?"}), encoding="utf-8")
    assert main(["lint", "d", "--root", str(tmp_path)]) == 1
    assert "nonsense" in capsys.readouterr().out


def test_new_does_not_accept_a_format_it_cannot_honour(tmp_path):
    """`new` has nowhere to persist a format choice -- the spec is deliberately
    format-agnostic and no manifest entry exists yet -- so accepting --format
    printed a promise that the subsequent render silently ignored."""
    with pytest.raises(SystemExit):
        main(["new", "d", "--kind", "concept", "--format", "mermaid", "--root", str(tmp_path)])


def test_new_reports_the_format_render_will_actually_use(tmp_path, capsys):
    assert main(["new", "d", "--kind", "flow", "--root", str(tmp_path)]) == 0
    assert "excalidraw" in capsys.readouterr().out


def _spec_at(root: Path, kind: str = "flow") -> Path:
    spec = root / "src" / "d.spec.yaml"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(
        yaml.safe_dump({"id": "d", "title": "T", "kind": kind, "question": "Q?",
                        "nodes": [{"id": "a", "label": "A"}], "edges": []}),
        encoding="utf-8",
    )
    return spec


def _capture_format(monkeypatch) -> list[str]:
    """Record the format compile_diagram is asked for, without rendering."""
    import designcore.cli as cli
    from designcore.manifest import DiagramEntry

    seen: list[str] = []

    def fake(spec, fmt, root, deps, hand_owned=False):
        seen.append(fmt)
        return DiagramEntry(
            id=spec.id, title=spec.title, kind=spec.kind, format=fmt, question=spec.question,
            spec=f"src/{spec.id}.spec.yaml", source=f"src/{spec.id}.{fmt}",
            rendered=[f"out/{fmt}/{spec.id}.svg"], embedded_in=[], hand_owned=hand_owned,
        )

    monkeypatch.setattr(cli, "compile_diagram", fake)
    return seen


def test_render_defaults_to_excalidraw_for_every_kind(tmp_path, monkeypatch):
    """A23: the per-kind default table is gone. No emitter reads spec.kind, so
    the table only ever encoded taste; excalidraw is the house default now and
    mermaid is requested when the diagram is going into a markdown file."""
    seen = _capture_format(monkeypatch)
    _spec_at(tmp_path, kind="sequence")
    assert main(["render", "d", "--root", str(tmp_path)]) == 0
    assert seen == ["excalidraw"]


def test_render_reuses_the_format_the_manifest_recorded(tmp_path, monkeypatch):
    """The choice is sticky: made once with --format, kept by later bare renders,
    so re-rendering never silently switches a diagram back to the default."""
    seen = _capture_format(monkeypatch)
    _spec_at(tmp_path)
    assert main(["render", "d", "--format", "drawio", "--root", str(tmp_path)]) == 0
    assert main(["render", "d", "--root", str(tmp_path)]) == 0
    assert seen == ["drawio", "drawio"]


def test_render_format_flag_overrides_the_recorded_format(tmp_path, monkeypatch):
    seen = _capture_format(monkeypatch)
    _spec_at(tmp_path)
    assert main(["render", "d", "--format", "mermaid", "--root", str(tmp_path)]) == 0
    assert main(["render", "d", "--format", "drawio", "--root", str(tmp_path)]) == 0
    assert seen == ["mermaid", "drawio"]
    entries = yaml.safe_load((tmp_path / "diagrams.yaml").read_text(encoding="utf-8"))["diagrams"]
    assert [(e["id"], e["format"]) for e in entries] == [("d", "drawio")]


def test_lint_checks_the_render_of_the_recorded_format(tmp_path):
    """Before A23 a diagram could hold several formats and _rendered_svg took
    whichever it found first, so lint bounds-checked one render and called the
    diagram clean. With one format per diagram the manifest decides."""
    _spec_at(tmp_path)
    clean = tmp_path / "out" / "mermaid" / "d.svg"
    clean.parent.mkdir(parents=True)
    clean.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600">'
        '<rect x="10" y="10" width="100" height="50"/></svg>',
        encoding="utf-8",
    )
    clipped = tmp_path / "out" / "excalidraw" / "d.svg"
    clipped.parent.mkdir(parents=True)
    clipped.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect x="10" y="10" width="500" height="50"/></svg>',
        encoding="utf-8",
    )
    (tmp_path / "diagrams.yaml").write_text(
        yaml.safe_dump({"version": 1, "diagrams": [{
            "id": "d", "title": "T", "kind": "flow", "format": "excalidraw", "question": "Q?",
            "spec": "src/d.spec.yaml", "source": "src/d.excalidraw",
            "rendered": ["out/excalidraw/d.svg"], "embedded_in": [],
        }]}),
        encoding="utf-8",
    )
    assert main(["lint", "d", "--root", str(tmp_path)]) == 1
