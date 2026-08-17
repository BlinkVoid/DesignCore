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
    assert main(["new", "d", "--kind", "concept", "--root", str(tmp_path)]) == 0
    assert "excalidraw" in capsys.readouterr().out
