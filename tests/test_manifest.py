from pathlib import Path

import hashlib
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


def test_check_with_fingerprints_is_content_not_time_based(tmp_path):
    """git does not preserve mtimes: on a fresh clone every file shares the
    checkout time, in arbitrary order. When a manifest records fingerprints,
    staleness must be decided by content alone — a consistent tree is clean
    no matter what order checkout wrote the files."""
    entry = _entry(
        source_sha256=hashlib.sha256(b"<mxfile/>").hexdigest(),
        spec_sha256=hashlib.sha256(b"id: x\n").hexdigest(),
    )
    root = _tree(tmp_path, entry)
    import os

    os.utime(root / "out" / "system-context.svg", (1, 1))  # older than everything
    assert check_manifest(root) == []


def test_check_flags_a_source_that_drifts_from_its_fingerprint(tmp_path):
    entry = _entry(source_sha256="0" * 64)
    root = _tree(tmp_path, entry)
    findings = check_manifest(root)
    assert [f.code for f in findings] == ["STALE_RENDER"]
    assert "fingerprint" in findings[0].message


def test_check_flags_a_spec_that_drifts_from_its_fingerprint(tmp_path):
    entry = _entry(spec_sha256="0" * 64)
    root = _tree(tmp_path, entry)
    assert [f.code for f in check_manifest(root)] == ["STALE_RENDER"]


def test_compile_diagram_records_fingerprints(tmp_path):
    from designcore.pipeline import Deps, compile_diagram
    from designcore.spec import load_spec

    spec_text = (
        "id: fp-demo\ntitle: Fp\nkind: context\nquestion: q?\n"
        "nodes:\n  - id: a\n    label: A\n"
    )
    (tmp_path / "src").mkdir()
    spec_file = tmp_path / "src" / "fp-demo.spec.yaml"
    spec_file.write_text(spec_text, encoding="utf-8")
    spec = load_spec(spec_file)

    def fake_render(src: Path, out: Path) -> list[Path]:
        out.mkdir(parents=True, exist_ok=True)
        target = out / (src.stem + ".svg")
        target.write_text("<svg/>", encoding="utf-8")
        return [target]

    deps = Deps(
        render_map={"mermaid": fake_render},
        layout=lambda spec: {},
        layout_groups=lambda spec: {},
    )
    entry = compile_diagram(spec, "mermaid", tmp_path, deps)
    assert entry.source_sha256 == hashlib.sha256(
        (tmp_path / "src" / "fp-demo.mmd").read_bytes()
    ).hexdigest()
    assert entry.spec_sha256 == hashlib.sha256(spec_text.encode("utf-8")).hexdigest()


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


def test_upsert_keys_on_id_alone_so_a_new_format_replaces_the_old():
    """Amendment A23: a diagram has exactly one format at a time. Re-rendering
    as another format replaces the entry rather than accumulating a second one;
    the abandoned files are then unreferenced and _orphaned_artifacts reports
    them."""
    manifest = Manifest(version=1, diagrams=[_entry(format="drawio")])
    updated = upsert(manifest, _entry(format="mermaid", source="src/system-context.mmd"))
    assert [(d.id, d.format) for d in updated.diagrams] == [("system-context", "mermaid")]


def test_upsert_collapses_a_manifest_left_multi_format_by_a18():
    """Manifests written before A23 hold one entry per (id, format). Replacing
    only the first match leaves the rest behind, and `render` then reads its
    sticky format off whichever entry happens to sit first — the example
    manifest re-rendered as mermaid when excalidraw was recorded further down."""
    manifest = Manifest(version=1, diagrams=[
        _entry(format="mermaid"), _entry(format="drawio"), _entry(format="excalidraw"),
    ])
    updated = upsert(manifest, _entry(format="excalidraw"))
    assert [(d.id, d.format) for d in updated.diagrams] == [("system-context", "excalidraw")]


def test_upsert_replaces_in_place_rather_than_reordering():
    """A format switch must not move the diagram to the end of the manifest —
    entry order is the file's reading order and belongs to the author."""
    manifest = Manifest(version=1, diagrams=[_entry(id="first"), _entry(id="second")])
    updated = upsert(manifest, _entry(id="first", format="mermaid"))
    assert [d.id for d in updated.diagrams] == ["first", "second"]
    assert updated.diagrams[0].format == "mermaid"
