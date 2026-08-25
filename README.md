# DesignCore

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

DesignCore turns a coordinate-free graph spec into a verified diagram — draw.io,
Mermaid, or Excalidraw — where the model never places a shape and nothing counts
as finished until it has actually rendered. It ships three agent skills
(`architecture-diagram`, `flow-diagram`, `concept-sketch`) that carry the
judgment layer on top.

> **What "verified" means here:** the spec compiled, every backend rendered
> successfully, and deterministic structural/density/geometry checks passed.
> It does **not** mean the diagram is visually correct or that it communicates
> well — judgment about content stays with you.

## Install

Requires [uv](https://docs.astral.sh/uv/).

```bash
# As an installable CLI tool
uv tool install git+https://github.com/BlinkVoid/DesignCore.git

# Or from a clone, for development
git clone https://github.com/BlinkVoid/DesignCore.git && cd DesignCore
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

### Platform notes

Verified on Linux. Portability caveats worth knowing before you rely on a
backend (full detail in
[docs/plans/2026-08-16-render-backend-findings.md](docs/plans/2026-08-16-render-backend-findings.md)):

| backend | caveat |
|---|---|
| `dot` (graphviz) | No sudo? Graphviz installs fine via `apt-get download` + `dpkg -x` into `~/.local` with a `GVBINDIR` wrapper — no root needed |
| `drawio` (snap) | Strict snap confinement: exports must run with input/output under `$HOME`, never `/tmp`; the snap wrapper already injects `--no-sandbox`. Headless export goes through `xvfb-run -a` when no `DISPLAY` is set |
| `mmdc` | Bundled Chromium may fail to start under AppArmor's userns restriction; the renderer prefers a system browser via puppeteer config and only falls back to `--no-sandbox` when no system browser exists |
| Excalidraw helper | Needs one `npm install --prefix src/designcore/render/js`; jsdom shims load before `@excalidraw/utils` |

macOS/Windows are untested for 0.1; the spec/lint layers are pure Python and
portable, the risk sits entirely in the external backends.

## Commands

| command | does |
|---|---|
| `designcore new <id> --kind <kind>` | scaffold a spec with the `question:` prompt |
| `designcore render <id>` | compile, render, and record a manifest entry |
| `designcore lint <id>` | structural, density, and geometry checks over spec and render |
| `designcore check` | validate `diagrams.yaml` against what is on disk |
| `designcore doctor` | report backend availability |

`--root` points at the diagram directory (default `docs/diagrams`). `render`
also takes `--format`, and the choice is sticky: it wins over the format the
manifest already records, which in turn wins over the `excalidraw` default. A
diagram has one format and one manifest entry at a time, so switching format
replaces the entry and leaves the old files for `check` to report as orphans.

Mermaid is the one to ask for when the diagram is going into a markdown file,
where it renders natively and diffs as text. See
[skills/_shared/references/format-selection.md](skills/_shared/references/format-selection.md).

## Example

A worked example lives in [`examples/docs/diagrams/`](examples/docs/diagrams/):
one spec, its excalidraw render, and a populated manifest.

```bash
uv run designcore render designcore-pipeline --root examples/docs/diagrams
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
