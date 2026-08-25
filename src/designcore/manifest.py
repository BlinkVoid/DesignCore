"""diagrams.yaml: what each diagram is for, and where its files live."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path

import yaml

from designcore.lint import Finding


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    # Content fingerprints of the inputs a render consumed. git does not
    # preserve mtimes, so staleness on a fresh clone is only decidable from
    # content; entries without fingerprints fall back to the mtime comparison.
    source_sha256: str = ""
    spec_sha256: str = ""

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
    """Insert or replace an entry, keyed by id.

    Amendment A23: a diagram has exactly one format at a time, so re-rendering
    as another format replaces the entry rather than accumulating a second one.
    The previous format's files are then referenced by nothing, which is
    precisely what `_orphaned_artifacts` reports — the switch is visible, and
    deleting the leftovers stays the author's decision.

    Replacement is in place: entry order is the manifest's reading order and
    belongs to whoever wrote it, so a format switch must not shuffle a diagram
    to the bottom of the file.

    Every entry for the id collapses into that one, not just the first match.
    Manifests written under A18 hold one entry per (id, format), and leaving the
    extras behind means `cli._cmd_render` reads its sticky format off whichever
    of them sits first — the shipped example re-rendered as mermaid when the
    excalidraw entry was further down the file.
    """
    diagrams = list(manifest.diagrams)
    matches = [index for index, existing in enumerate(diagrams) if existing.id == entry.id]
    if not matches:
        diagrams.append(entry)
        return replace(manifest, diagrams=diagrams)

    diagrams[matches[0]] = entry
    for index in reversed(matches[1:]):
        del diagrams[index]
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

        # Staleness is content-first: if the render recorded fingerprints of
        # its inputs, drift is a hash mismatch — decidable on a fresh clone,
        # where git has flattened every mtime to checkout time. Entries
        # written before fingerprints existed fall back to comparing mtimes.
        fingerprinted = bool(entry.source_sha256 or entry.spec_sha256)

        for rendered in entry.rendered:
            target = root / rendered
            if not target.exists():
                findings.append(
                    Finding("MISSING_RENDER", "error", f"render {rendered} is missing", entry.id)
                )
            elif fingerprinted and (
                (entry.source_sha256 and _sha256(source) != entry.source_sha256)
                or (
                    entry.spec_sha256
                    and spec.exists()
                    and _sha256(spec) != entry.spec_sha256
                )
            ):
                findings.append(
                    Finding(
                        "STALE_RENDER",
                        "warning",
                        f"{rendered} differs from the render's recorded input "
                        "fingerprints; re-run designcore render",
                        entry.id,
                    )
                )
            elif not fingerprinted:
                # Measured against the spec as well as the emitted source: editing a
                # spec without re-rendering leaves the source untouched, so comparing
                # only against it reports "clean" for exactly the drift that matters.
                authored = max([source.stat().st_mtime] + ([spec.stat().st_mtime] if spec.exists() else []))
                if target.stat().st_mtime < authored:
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
