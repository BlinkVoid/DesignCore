# DesignCore

DesignCore turns a coordinate-free graph spec into a verified diagram — draw.io,
Mermaid, or Excalidraw — where the model never places a shape and nothing counts
as finished until it has actually rendered. It ships three agent skills
(`architecture-diagram`, `flow-diagram`, `concept-sketch`) that carry the
judgment layer on top.

## Install

```bash
uv sync
uv run designcore doctor
```

`doctor` reports the external backends and the exact command to install each:

| backend | used for |
|---|---|
| `mmdc` (mermaid-cli) | rendering Mermaid |
| `dot` (graphviz) | computing all node geometry |
| `drawio` (snap) | exporting .drawio to SVG/PNG |
| `node` | the Excalidraw SVG export helper |

The Excalidraw helper also needs its own dependencies once:

```bash
npm install --prefix src/designcore/render/js
```

> `doctor` proves a backend is on `PATH`, not that it can render. A backend can
> pass `doctor` and still fail — install-time and render-time are different
> questions.

## Commands

| command | does |
|---|---|
| `designcore new <id> --kind <kind>` | scaffold a spec with the `question:` prompt |
| `designcore render <id>` | compile, render, and record a manifest entry |
| `designcore lint <id>` | structural, density, and geometry checks over spec and render |
| `designcore check` | validate `diagrams.yaml` against what is on disk |
| `designcore doctor` | report backend availability |

`--root` points at the diagram directory (default `docs/diagrams`); `--format`
overrides the default chosen from the spec's `kind`.

## Example

A worked example lives in [`examples/docs/diagrams/`](examples/docs/diagrams/):
one spec compiled to all three formats, with renders and a populated manifest.

```bash
uv run designcore render designcore-pipeline --root examples/docs/diagrams --format mermaid
```

## The two rules

- **The model never writes coordinates.** `x`, `y`, `width`, `height` and
  `position` are rejected at parse time. Geometry comes from Graphviz.
- **No diagram is complete without a successful render.** A missing backend
  raises `BackendMissing` naming its install command; it never degrades quietly
  into an unverified result.

## Further reading

- [ARCHITECTURE.md](ARCHITECTURE.md) — layer map and module layout.
- [docs/plans/2026-08-16-designcore-design.md](docs/plans/2026-08-16-designcore-design.md)
  — the design spec, and why each decision was made.
- [docs/plans/2026-08-16-render-backend-findings.md](docs/plans/2026-08-16-render-backend-findings.md)
  — what each render backend actually does on real hardware.
