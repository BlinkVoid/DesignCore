"""spec in, verified diagram out."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from designcore.emit.drawio import emit_drawio
from designcore.emit.excalidraw import emit_excalidraw
from designcore.emit.mermaid import emit_mermaid
from designcore.layout import Placement, layout_all
from designcore.lint import Finding
from designcore.lint.density import check_density
from designcore.lint.geometry import check_geometry, check_svg_bounds
from designcore.lint.structural import check_structure
from designcore.manifest import DiagramEntry
from designcore.render.drawio import render_drawio
from designcore.render.excalidraw import render_excalidraw
from designcore.render.mermaid import render_mermaid
from designcore.spec import DiagramSpec

SUFFIXES = {"mermaid": ".mmd", "drawio": ".drawio", "excalidraw": ".excalidraw"}

# Formats whose output files carry the Graphviz placements verbatim. Mermaid
# is absent on purpose: it runs its own layout at render time, so checking
# placements against a mermaid diagram lints geometry no output file uses.
GEOMETRY_FORMATS = frozenset({"drawio", "excalidraw"})


@dataclass(frozen=True)
class Deps:
    """Injected backends, so the pipeline is testable without any binary.

    Amendment A4 removed the `convert` field: the drawio emitter is owned and
    Graphviz-driven, so nothing converts from mermaid any more.
    """

    render_map: dict[str, Callable[[Path, Path], list[Path]]]
    layout: Callable[[DiagramSpec], dict[str, Placement]]
    layout_groups: Callable[[DiagramSpec], dict[str, Placement]]
    layout_edges: Callable[[DiagramSpec], dict] | None = None

    @classmethod
    def default(cls) -> "Deps":
        # Both callables read from one memoized layout_all, so the drawio path
        # -- which needs nodes and groups -- runs dot once instead of twice,
        # and the two results provably describe the same layout. DiagramSpec
        # is a frozen dataclass of tuples, so it is hashable as a cache key.
        @lru_cache(maxsize=1)
        def _layout_both(spec: DiagramSpec) -> tuple[dict, dict, dict]:
            return layout_all(spec)

        return cls(
            render_map={
                "mermaid": render_mermaid,
                "drawio": render_drawio,
                "excalidraw": render_excalidraw,
            },
            layout=lambda spec: _layout_both(spec)[0],
            layout_groups=lambda spec: _layout_both(spec)[1],
            layout_edges=lambda spec: _layout_both(spec)[2],
        )


def _source_text(spec: DiagramSpec, fmt: str, deps: Deps) -> str:
    if fmt == "mermaid":
        return emit_mermaid(spec)
    if fmt == "drawio":
        return emit_drawio(spec, deps.layout(spec), deps.layout_groups(spec))
    if fmt == "excalidraw":
        routes = deps.layout_edges(spec) if deps.layout_edges else None
        return json.dumps(emit_excalidraw(spec, deps.layout(spec), routes), indent=2)
    raise ValueError(f"unknown format {fmt!r}; expected one of {sorted(SUFFIXES)}")


def compile_diagram(
    spec: DiagramSpec,
    fmt: str,
    out_root: Path,
    deps: Deps,
    hand_owned: bool = False,
) -> DiagramEntry:
    """Compile, write, and render one diagram. Returns its manifest entry."""
    out_root = Path(out_root)
    source_path = out_root / "src" / (spec.id + SUFFIXES[fmt])

    if hand_owned and source_path.exists():
        raise PermissionError(
            f"{source_path} is marked hand_owned; refusing to overwrite hand edits. "
            "Fold the change back into the spec or clear hand_owned first."
        )

    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(_source_text(spec, fmt, deps), encoding="utf-8")

    # Per-format output directory: every renderer names its output from the
    # source stem, which is the diagram id in all three formats, so a shared
    # out/ makes the second render silently clobber the first.
    rendered = deps.render_map[fmt](source_path, out_root / "out" / fmt)

    return DiagramEntry(
        id=spec.id,
        title=spec.title,
        kind=spec.kind,
        format=fmt,
        question=spec.question,
        spec=str(Path("src") / (spec.id + ".spec.yaml")),
        source=str(source_path.relative_to(out_root)),
        rendered=[str(p.relative_to(out_root)) for p in rendered],
        hand_owned=hand_owned,
    )


def lint_diagram(
    spec: DiagramSpec,
    placements: dict[str, Placement],
    svg_path: Path | None,
    groups: dict[str, Placement] | None = None,
) -> list[Finding]:
    """Run every deterministic check over one diagram.

    Group boxes are checked separately from node placements, never merged
    with them: a container encloses its members by construction, so a single
    combined overlap pass reports every group as colliding with everything it
    holds.
    """
    findings = check_structure(spec) + check_density(spec)
    findings += check_geometry(list(placements.values()))
    if groups:
        findings += check_geometry(list(groups.values()))
    if svg_path is not None and Path(svg_path).exists():
        findings += check_svg_bounds(Path(svg_path))
    return findings
