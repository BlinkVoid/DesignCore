from pathlib import Path

import pytest

from designcore.manifest import (
    DiagramEntry,
    Manifest,
    check_manifest,
    load_manifest,
    save_manifest,
    upsert,
)


def _entry(**overrides) -> DiagramEntry:
    base = dict(
        id="system-context", title="System context", kind="context", format="drawio",
        question="Which external systems does the platform talk to?",
        spec="src/system-context.spec.yaml", source="src/system-context.drawio",
        rendered=["out/system-context.svg"], embedded_in=["../architecture.md"],
    )
    return DiagramEntry(**{**base, **overrides})


def _tree(tmp_path: Path, entry: DiagramEntry) -> Path:
    root = tmp_path / "docs" / "diagrams"
    (root / "src").mkdir(parents=True)
    (root / "out").mkdir()
    (root / entry.spec).write_text("id: x\n", encoding="utf-8")
    (root / entry.source).write_text("<mxfile/>", encoding="utf-8")
    for rendered in entry.rendered:
        (root / rendered).write_text("<svg/>", encoding="utf-8")
    (tmp_path / "docs" / "architecture.md").write_text("# Arch\n", encoding="utf-8")
    save_manifest(Manifest(version=1, diagrams=[entry]), root / "diagrams.yaml")
    return root


def test_round_trips_through_yaml(tmp_path):
    path = tmp_path / "diagrams.yaml"
    save_manifest(Manifest(version=1, diagrams=[_entry()]), path)
    loaded = load_manifest(path)
    assert loaded.version == 1
    assert loaded.diagrams[0] == _entry()


def test_upsert_replaces_by_id_without_appending(tmp_path):
    manifest = Manifest(version=1, diagrams=[_entry()])
    updated = upsert(manifest, _entry(title="Renamed"))
    assert len(updated.diagrams) == 1
    assert updated.diagrams[0].title == "Renamed"


def test_upsert_appends_a_new_id():
    manifest = Manifest(version=1, diagrams=[_entry()])
    updated = upsert(manifest, _entry(id="other"))
    assert [d.id for d in updated.diagrams] == ["system-context", "other"]


def test_check_passes_on_a_complete_tree(tmp_path):
    assert check_manifest(_tree(tmp_path, _entry())) == []


def test_check_flags_missing_source_file(tmp_path):
    root = _tree(tmp_path, _entry())
    (root / "src" / "system-context.drawio").unlink()
    assert [f.code for f in check_manifest(root)] == ["MISSING_SOURCE"]


def test_check_flags_missing_render(tmp_path):
    root = _tree(tmp_path, _entry())
    (root / "out" / "system-context.svg").unlink()
    assert [f.code for f in check_manifest(root)] == ["MISSING_RENDER"]


def test_check_flags_stale_render(tmp_path):
    root = _tree(tmp_path, _entry())
    source = root / "src" / "system-context.drawio"
    rendered = root / "out" / "system-context.svg"
    import os
    os.utime(rendered, (1, 1))
    os.utime(source, (10_000, 10_000))
    assert [f.code for f in check_manifest(root)] == ["STALE_RENDER"]


def test_check_flags_broken_embed_target(tmp_path):
    root = _tree(tmp_path, _entry(embedded_in=["../nowhere.md"]))
    assert [f.code for f in check_manifest(root)] == ["BROKEN_EMBED"]


def test_entry_requires_a_question():
    with pytest.raises(ValueError, match="question"):
        _entry(question="")


def test_check_flags_a_render_older_than_its_spec(tmp_path):
    """Editing the spec without re-rendering is the drift the manifest exists
    to catch, but staleness was only measured against the emitted source --
    which does not change until you re-render."""
    root = _tree(tmp_path, _entry())
    import os
    os.utime(root / "out" / "system-context.svg", (1, 1))
    os.utime(root / "src" / "system-context.drawio", (1, 1))
    os.utime(root / "src" / "system-context.spec.yaml", (10_000, 10_000))
    assert [f.code for f in check_manifest(root)] == ["STALE_RENDER"]


def test_check_flags_a_missing_spec(tmp_path):
    root = _tree(tmp_path, _entry())
    (root / "src" / "system-context.spec.yaml").unlink()
    assert [f.code for f in check_manifest(root)] == ["MISSING_SPEC"]


def test_check_flags_artifacts_no_entry_references(tmp_path):
    """Re-rendering under a different format leaves the previous source and
    renders on disk, unreferenced. check could not see them, so a doc still
    embedding the old path kept showing a stale picture."""
    root = _tree(tmp_path, _entry())
    (root / "src" / "system-context.mmd").write_text("flowchart LR\n", encoding="utf-8")
    (root / "out" / "system-context.png").write_text("stale", encoding="utf-8")
    findings = check_manifest(root)
    assert [f.code for f in findings] == ["ORPHANED_ARTIFACT", "ORPHANED_ARTIFACT"]
    assert all(f.severity == "warning" for f in findings)
    assert {f.subject for f in findings} == {
        "src/system-context.mmd",
        "out/system-context.png",
    }


def test_check_ignores_the_manifest_and_referenced_files(tmp_path):
    assert check_manifest(_tree(tmp_path, _entry())) == []


def test_upsert_keys_on_id_and_format():
    """Amendment A13 gave each format its own out/ directory so renders coexist;
    the manifest has to describe that, or rendering a second format silently
    drops the first entry and orphans its files."""
    manifest = Manifest(version=1, diagrams=[_entry(format="drawio")])
    updated = upsert(manifest, _entry(format="mermaid", source="src/system-context.mmd"))
    assert [(d.id, d.format) for d in updated.diagrams] == [
        ("system-context", "drawio"),
        ("system-context", "mermaid"),
    ]


def test_upsert_still_replaces_the_same_id_and_format():
    manifest = Manifest(version=1, diagrams=[_entry(format="drawio")])
    updated = upsert(manifest, _entry(format="drawio", title="Renamed"))
    assert len(updated.diagrams) == 1
    assert updated.diagrams[0].title == "Renamed"
