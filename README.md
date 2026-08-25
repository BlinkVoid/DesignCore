# ✎ DesignCore

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/BlinkVoid/DesignCore/actions/workflows/tests.yml/badge.svg)](https://github.com/BlinkVoid/DesignCore/actions/workflows/tests.yml)

> 🌐 [Project website](https://blinkvoid.github.io/DesignCore/)

> **Verified diagrams for documentation** — draw.io, Mermaid, or Excalidraw,
> from a spec your AI agent can actually be trusted to write.

DesignCore turns a coordinate-free graph spec into a verified diagram, where
the model **never places a shape** and nothing counts as finished until it has
actually rendered. It ships three agent skills (`architecture-diagram`,
`flow-diagram`, `concept-sketch`) that carry the judgment layer on top.

---

## 🧭 What "verified" means

> The spec compiled cleanly, every backend rendered successfully, and
> deterministic structural/density/geometry checks passed.
>
> It does **not** mean the diagram is visually correct or that it communicates
> well — judgment about content stays with you.

---

## ⚖️ The two rules

| | Rule | Enforcement |
|---|---|---|
| 1️⃣ | **The model never writes coordinates.** | `x`, `y`, `width`, `height`, `position` are rejected at parse time. Geometry comes from Graphviz — always. |
| 2️⃣ | **No diagram is complete without a successful render.** | A missing backend raises `BackendMissing` naming its install command; a spec never degrades quietly into an unverified result. |

LLMs are good at structure and bad at pixels. DesignCore splits the job along
exactly that line: *judgment lives in the skills, mechanism lives in the
package.*

---

## 🚀 Install

Requires [uv](https://docs.astral.sh/uv/).

```bash
# As an installable CLI tool (from GitHub today; PyPI pending)
uv tool install git+https://github.com/BlinkVoid/DesignCore.git

# Or from a clone, for development
git clone https://github.com/BlinkVoid/DesignCore.git && cd DesignCore
uv sync
uv run designcore doctor
```

### Render backends

`designcore doctor` reports what's available and names the exact install
command for anything missing:

| backend | used for |
|---|---|
| `mmdc` (mermaid-cli) | rendering Mermaid |
| `dot` (graphviz) | computing **all** node geometry |
| `drawio` (snap) | exporting .drawio to SVG/PNG |
| `node` | the Excalidraw SVG export helper |

The Excalidraw helper needs its own dependencies once:

```bash
npm install --prefix src/designcore/render/js
```

<details>
<summary><strong>🔧 Platform notes & portability caveats</strong></summary>

Verified on Linux. Full detail in
[docs/plans/2026-08-16-render-backend-findings.md](docs/plans/2026-08-16-render-backend-findings.md).

| backend | caveat |
|---|---|
| `dot` (graphviz) | No sudo? Graphviz installs fine via `apt-get download` + `dpkg -x` into `~/.local` with a `GVBINDIR` wrapper |
| `drawio` (snap) | Strict snap confinement: exports must run under `$HOME`, never `/tmp`; wrapper already injects `--no-sandbox`; headless export via `xvfb-run -a` |
| `mmdc` | Bundled Chromium may fail under AppArmor's userns restriction; renderer prefers a system browser, falls back to `--no-sandbox` only when none exists |
| Excalidraw helper | jsdom shims load before `@excalidraw/utils` |

macOS/Windows are untested for 0.1; spec/lint are pure Python — the risk sits
entirely in the external backends.

</details>

---

## 🛠️ Commands

| command | does |
|---|---|
| `designcore new <id> --kind <kind>` | scaffold a spec with the `question:` prompt |
| `designcore render <id>` | compile → lay out → render → lint, and record a manifest entry |
| `designcore lint <id>` | structural, density, and geometry checks over spec and render |
| `designcore check` | validate `diagrams.yaml` against what is on disk (content-fingerprinted, clone-safe) |
| `designcore doctor` | report backend availability + install commands |

`--root` points at the diagram directory (default `docs/diagrams`). `render`
also takes `--format`, and the choice is **sticky**: an explicit flag wins over
the manifest's recorded format, which wins over the `excalidraw` default. A
diagram has one format and one manifest entry at a time — switching format
replaces the entry, and `check` reports the abandoned files as orphans.

💡 Mermaid is the right choice when the diagram lives in markdown: it renders
natively on GitHub and diffs as text. See
[skills/_shared/references/format-selection.md](skills/_shared/references/format-selection.md).

---

## 📐 How it fits together

```
.spec.yaml ──► parse_spec ──► layout_spec (Graphviz) ──┬──► emit_* ──► source file
                                                       │                  │
   rejects coordinates                                 │                  ▼
   at parse time                                       │              render_* ──► svg + png
                                                       │                  │
                                                       └────────────── lint ◄┘
                                                                          │
                                                                     diagrams.yaml
```

Judgment lives in the skills; mechanism lives in the package. The package
makes no aesthetic decisions, and the skills compute no geometry.

---

## 📁 Example

A worked example lives in [`examples/docs/diagrams/`](examples/docs/diagrams/):
one spec, its excalidraw render, and a populated manifest.

```bash
uv run designcore render designcore-pipeline --root examples/docs/diagrams
```

---

## 📚 Further reading

| doc | contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | layer map and module layout |
| [docs/plans/2026-08-16-designcore-design.md](docs/plans/2026-08-16-designcore-design.md) | the design spec — and why each decision was made |
| [docs/plans/2026-08-16-render-backend-findings.md](docs/plans/2026-08-16-render-backend-findings.md) | what each render backend actually does on real hardware |

---

## 📄 License

[MIT](LICENSE)
