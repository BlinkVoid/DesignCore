from pathlib import Path

import yaml

from designcore.cli import main


def test_new_scaffolds_a_spec_with_the_question_prompt(tmp_path, capsys):
    code = main(["new", "request-flow", "--kind", "flow", "--root", str(tmp_path), "--format", "mermaid"])
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
