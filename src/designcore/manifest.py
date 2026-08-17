"""diagrams.yaml: what each diagram is for, and where its files live."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path

import yaml

from designcore.lint import Finding


@dataclass(frozen=True)
class DiagramEntry:
    id: str
    title: str
    kind: str
    format: str
    question: str
    spec: str
    source: str
    rendered: list[str] = field(default_factory=list)
    embedded_in: list[str] = field(default_factory=list)
    hand_owned: bool = False
    generated_by: str = "designcore"
    generated_at: str = field(default_factory=lambda: date.today().isoformat())

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError(
                f"diagram {self.id!r} has no question; a diagram that cannot state "
                "the one question it answers should be split or deleted"
            )


@dataclass(frozen=True)
class Manifest:
    version: int
    diagrams: list[DiagramEntry]


def load_manifest(path: Path) -> Manifest:
    with Path(path).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return Manifest(
        version=int(data.get("version", 1)),
        diagrams=[DiagramEntry(**d) for d in data.get("diagrams", [])],
    )


def save_manifest(manifest: Manifest, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": manifest.version, "diagrams": [asdict(d) for d in manifest.diagrams]}
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def upsert(manifest: Manifest, entry: DiagramEntry) -> Manifest:
    """Insert or replace an entry, keyed by (id, format).

    Not by id alone: amendment A13 gave each format its own `out/` directory
    so a diagram can exist in several formats at once, and a manifest keyed
    only by id would drop the previous entry and orphan its files on the
    second render.
    """
    diagrams = list(manifest.diagrams)
    for index, existing in enumerate(diagrams):
        if (existing.id, existing.format) == (entry.id, entry.format):
            diagrams[index] = entry
            return replace(manifest, diagrams=diagrams)
    diagrams.append(entry)
    return replace(manifest, diagrams=diagrams)


def check_manifest(root: Path) -> list[Finding]:
    """Validate that every manifest entry matches what is on disk."""
    root = Path(root)
    manifest = load_manifest(root / "diagrams.yaml")
    findings: list[Finding] = []

    for entry in manifest.diagrams:
        spec = root / entry.spec
        if not spec.exists():
            findings.append(
                Finding("MISSING_SPEC", "error", f"spec {entry.spec} is missing", entry.id)
            )

        source = root / entry.source
        if not source.exists():
            findings.append(
                Finding("MISSING_SOURCE", "error", f"source {entry.source} is missing", entry.id)
            )
            continue

        # Measured against the spec as well as the emitted source: editing a
        # spec without re-rendering leaves the source untouched, so comparing
        # only against it reports "clean" for exactly the drift that matters.
        authored = max(
            [source.stat().st_mtime] + ([spec.stat().st_mtime] if spec.exists() else [])
        )

        for rendered in entry.rendered:
            target = root / rendered
            if not target.exists():
                findings.append(
                    Finding("MISSING_RENDER", "error", f"render {rendered} is missing", entry.id)
                )
            elif target.stat().st_mtime < authored:
                findings.append(
                    Finding(
                        "STALE_RENDER",
                        "warning",
                        f"{rendered} is older than its spec or source; "
                        "re-run designcore render",
                        entry.id,
                    )
                )

        for embed in entry.embedded_in:
            if not (root / embed).exists():
                findings.append(
                    Finding("BROKEN_EMBED", "warning", f"embed target {embed} is missing", entry.id)
                )

    findings.extend(_orphaned_artifacts(root, manifest))
    return findings


def _orphaned_artifacts(root: Path, manifest: Manifest) -> list[Finding]:
    """Flag files under src/ and out/ that no entry references.

    Re-rendering a diagram in a different format leaves the previous source
    and renders behind. Nothing points at them, so a document still embedding
    the old path keeps showing a stale picture that `check` cannot see.
    Reported, never deleted -- removing a file a reader may still link to is
    the author's call.
    """
    referenced = {
        (root / path).resolve()
        for entry in manifest.diagrams
        for path in (entry.spec, entry.source, *entry.rendered)
    }

    findings: list[Finding] = []
    for directory in ("src", "out"):
        base = root / directory
        if not base.is_dir():
            continue
        for found in sorted(base.rglob("*")):
            if found.is_dir() or found.resolve() in referenced:
                continue
            relative = found.relative_to(root)
            findings.append(
                Finding(
                    "ORPHANED_ARTIFACT",
                    "warning",
                    f"{relative} is not referenced by any diagram entry; "
                    "left over from a previous format or a deleted diagram",
                    str(relative),
                )
            )
    return findings
