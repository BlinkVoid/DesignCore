# DesignCore architecture

For *why* any of this is shaped the way it is, read the design spec:
[docs/plans/2026-08-16-designcore-design.md](docs/plans/2026-08-16-designcore-design.md).
This page is the map, not the rationale — the decision table lives there and is
deliberately not duplicated here.

## Layers

```
skills/architecture-diagram    flow-diagram    concept-sketch      ← judgment
skills/_shared/references/     format-selection · legibility · pipeline
                               mermaid · drawio · excalidraw
src/designcore/                spec · layout · emit · render · lint · manifest · cli
external                       mermaid-cli · graphviz · drawio CLI · node (+jsdom) · chrome
```

Judgment lives in the skills; mechanism lives in the package. The package makes
no aesthetic decisions, and the skills compute no geometry.

## Modules

| module | responsibility |
|---|---|
| `spec.py` | the graph spec model and its validation; rejects coordinates |
| `layout.py` | Graphviz invocation; node placements and group bounding boxes |
| `emit/` | `mermaid.py`, `drawio.py`, `excalidraw.py` — spec + placements → source |
| `render/` | one module per backend, plus `js/` (the Excalidraw Node helper) |
| `lint/` | `structural.py`, `density.py`, `geometry.py` → `Finding` |
| `manifest.py` | `diagrams.yaml` read/write and integrity checks |
| `pipeline.py` | compile → render → lint, with backends injected via `Deps` |
| `cli.py` | `new` · `render` · `lint` · `check` · `doctor` |

Data flows one way:

```
.spec.yaml → parse_spec → layout_spec ─┐
                                       ├→ emit_* → source file → render_* → svg + png
                                       │                                       │
                                       └────────────── lint ───────────────────┘
                                                        ↓
                                                   diagrams.yaml
```

## The central invariant

**The model never writes x/y, and nothing is complete without a render.**

Both halves are enforced in code, not convention. `spec.py` raises `SpecError`
on any geometry key in a spec file, so there is no path by which a coordinate
reaches an emitter except from Graphviz. Every renderer raises `BackendMissing`
with an install command rather than returning a partial result, and
`compile_diagram` renders before it returns a manifest entry — a diagram cannot
be recorded as existing without having been drawn.

The corollary is that lint is necessary but never sufficient. Geometry checks
run over real placements and real rendered SVG, but a diagram can pass every
check and still be unreadable, so the pipeline ends with a human or model
looking at the PNG. See
[skills/_shared/references/pipeline.md](skills/_shared/references/pipeline.md).

## Testing

Unit tests inject `run` and `which` at every subprocess boundary, so the suite
needs no network and no external binary. `tests/test_end_to_end.py` is the
exception: it drives the real CLI against real `mmdc` and `dot`, and it is meant
to run, not skip.
