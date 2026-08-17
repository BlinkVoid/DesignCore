# DesignCore — Design Spec

- **Date:** 2026-08-16
- **Status:** Implemented in v1 — see README.md
- **Scope:** DesignCore v1 — the diagramming subsystem (first skill family)
- **Next artifact:** implementation plan (`docs/plans/2026-08-16-designcore-implementation-plan.md`)

---

## 1. Purpose

Documentation is unclear when it describes structure in prose that only a picture can carry.
DesignCore exists to make an AI agent produce **hand-crafted, verified diagrams** — draw.io,
Mermaid, and Excalidraw — as a routine part of writing documentation, at a quality level that
survives review.

The problem is not "can a model emit diagram syntax". Models emit diagram syntax easily. The
problem is that the output is usually wrong in two specific ways:

1. **Geometry** — overlapping nodes, clipped labels, stacked edges, off-canvas content.
   This happens whenever a model places coordinates by hand.
2. **Judgment** — one diagram trying to answer five questions, wrong notation for the genre,
   no visual hierarchy, detail at the wrong altitude.

DesignCore attacks (1) with determinism and (2) with skills that carry explicit discipline.

### Success criteria

- A diagram request produces a source file, a rendered export, and a manifest entry — all
  committed to the target project's repo, embeddable in its docs.
- No diagram is reported complete without a successful render.
- Structural defects (dangling edges, overlaps, truncation) are caught mechanically, not by luck.
- A later agent can regenerate or amend any diagram without re-deriving why it exists.

---

## 2. Prior art (research, 2026-08-16)

The draw.io space is no longer empty. This materially shaped the design.

**Official `@drawio/mcp`** (jgraph, draw.io's own maintainers) exposes `open_drawio_xml`,
`open_drawio_csv`, `open_drawio_mermaid`, `search_shapes` (~10k AWS/Azure/GCP/Cisco/K8s/BPMN
stencils auto-discovered from the real editor sidebar), and `list_pages` / `get_page` /
`set_page` for multi-page `.drawio` files. It supports libavoid obstacle-avoiding edge routing
and an optional ELK layered-layout pass. ~~Critically, **it accepts Mermaid as input and returns
editable native mxGraph XML**.~~ **Disproved by the 2026-08-16 probe** (see
`2026-08-16-render-backend-findings.md` §2): the tool is stdio-only and `open_drawio_mermaid`
opens a browser editor URL rather than returning mxGraph XML to the caller; the drawio emit
path is therefore an owned Graphviz-driven emitter (§6). Its desktop-Electron integration is
flagged experimental (upstream CSP issue); the non-Electron path is the one to use.

**`Agents365-ai/drawio-skill`** is the most built-out community skill: 11 presets (UML, C4,
BPMN, network), 13 extractors (Python/JS/Go/Rust import graphs, Terraform, Kubernetes,
docker-compose, SQL DDL, OpenAPI, CI DAGs), Graphviz autolayout, a deterministic linter, and a
**vision self-check loop** — export PNG, read it back, auto-fix overlaps and clipped labels
across bounded rounds.

**Mermaid** is the cheapest and most reliable substrate: models are heavily trained on it, it is
token-light, and it renders natively on GitHub, in Obsidian, and in Claude artifacts. Its failure
modes are syntax errors and over-dense graphs. `MermaidSeqBench` (arXiv 2511.14967) exists as an
NL→Mermaid correctness benchmark. The accepted workflow everywhere is generate → render → verify.

**Excalidraw** stores plain JSON, so emission is trivial; legibility is the hard part.
`yctimlin/mcp_excalidraw` (MCP server + skill, 26 tools, live canvas sync, screenshot-based
self-correction) is the reference implementation.

**The convergent lesson:** every mature tool moves geometry to a deterministic layout engine and
validates by rendering. None of them trust model-placed coordinates. DesignCore adopts this as
its central invariant rather than rediscovering it.

Sources:
[@drawio/mcp](https://www.npmjs.com/package/@drawio/mcp) ·
[jgraph/drawio-mcp](https://github.com/jgraph/drawio-mcp) ·
[Agents365-ai/drawio-skill](https://github.com/Agents365-ai/drawio-skill) ·
[yctimlin/mcp_excalidraw](https://github.com/yctimlin/mcp_excalidraw) ·
[MermaidSeqBench](https://arxiv.org/pdf/2511.14967)

---

## 3. Decisions and rationale

| # | Decision | Rationale | Rejected alternative |
|---|---|---|---|
| D1 | **Judgment layer over existing tools.** DesignCore owns what to draw, when, and whether it reads well. Rendering (drawio CLI, mmdc) and shape catalogs remain delegated; layout is Graphviz; the drawio and excalidraw emitters are owned (the drawio one became owned after the 2026-08-16 probe disproved the upstream converter). | The rendering problem is solved and actively maintained by draw.io's own team. The judgment problem is not solved by anyone and is what actually makes documentation clearer. | Building a full generator stack — rebuilds ELK/libavoid/shape indexes we would then have to maintain against upstream. |
| D2 | **Skills named by purpose, format chosen inside.** `architecture-diagram`, `flow-diagram`, `concept-sketch`, sharing one format/mechanics layer. | Matches how diagrams are actually requested ("draw the request flow", not "make me a mermaid"). Format is an implementation detail the skill decides. Shared layer prevents triplicated format mechanics. | Format-named skills (`mermaid`/`drawio`/`excalidraw`) — forces the caller to pre-decide the thing the skill is best positioned to judge. |
| D3 | **The model never writes x/y.** Coordinates come from a layout engine, always. | This is the single documented cause of bad LLM diagrams across all prior art. | Trusting model placement with a fix-up pass — fights the failure instead of removing it. |
| D4 | **Render + deterministic lint + bounded vision self-check.** | Lint catches what is nameable; the vision pass catches hierarchy and readability, which no linter can express. Bounding to 2 rounds keeps cost finite. | Lint-only (nothing judges whether it reads well); layout-engine-only (silent failures ship). |
| D5 | **Sources + rendered exports + manifest, in the target repo.** | Diagrams-as-code: versioned, diffable, reviewable in PRs. The manifest preserves *intent*, which is the part a regenerating agent cannot recover from the file. | Inline-only mermaid (loses fidelity for complex diagrams and leaves the vision pass nothing on disk to check). |
| D6 | **Python package + CLI + `skills/`, registered in GearCore.** | Matches GearCore/DevCore house style. The determinism lives in tested code, not in prose the agent re-improvises each run. | Skills-only repo — the reliability-critical part would live in untested loose scripts. |
| D7 | **No diagram is done until it renders.** Missing render backends produce a loud failure, never silent success. | An unverified diagram is worse than no diagram: it looks authoritative and is wrong. | Best-effort degradation — reintroduces exactly the failure mode DesignCore exists to prevent. |

---

## 4. Architecture

```
skills/architecture-diagram    flow-diagram    concept-sketch      ← judgment
skills/_shared/references/     format-selection · legibility · mermaid · drawio · excalidraw
src/designcore/                spec · layout · emit · render · lint · manifest · cli
external                       mermaid-cli · graphviz · drawio CLI · node (+jsdom) · chrome
```

### Repository layout

```
DesignCore/
├── pyproject.toml            # uv-managed, matches GearCore/DevCore
├── uv.lock
├── README.md
├── ARCHITECTURE.md           # points at this spec, does not restate it
├── docs/plans/
│   ├── 2026-08-16-designcore-design.md          # this file
│   └── 2026-08-16-designcore-implementation-plan.md
├── src/designcore/
│   ├── cli.py                # new · render · lint · check · doctor
│   ├── spec.py               # graph spec model + validation
│   ├── layout.py             # Graphviz invocation, rank/group handling
│   ├── manifest.py           # diagrams.yaml read/write/validate
│   ├── lint/
│   │   ├── structural.py     # dangling edges, dup IDs, orphan nodes
│   │   ├── geometry.py       # overlap, off-canvas, clipping, crossing density
│   │   └── density.py        # node/edge count thresholds → "split this"
│   ├── emit/
│   │   ├── mermaid.py
│   │   ├── drawio.py         # owned emitter (Graphviz placements → mxGraph XML)
│   │   └── excalidraw.py     # owned emitter (no upstream converter exists)
│   └── render/
│       ├── mermaid.py        # mmdc
│       ├── drawio.py         # drawio CLI export (xvfb if needed)
│       ├── excalidraw.py     # jsdom helper (js/) + chrome rasterization
│       └── js/                # shipped Node export helper, pinned deps
├── skills/
│   ├── _shared/references/
│   ├── architecture-diagram/  { SKILL.md, manifest.json }
│   ├── flow-diagram/          { SKILL.md, manifest.json }
│   └── concept-sketch/        { SKILL.md, manifest.json }
└── tests/
```

Skill bundles follow `GearCore/SKILL_SCHEMA.md` (SKILL.md required; manifest.json for category,
triggers, MCP bindings) and are registered into `~/.config/gearcore/skills/` so
`gearcore list-skills` surfaces them.

---

## 5. The graph spec

The authoring substrate. The model writes this; it contains **no coordinates**.

```yaml
id: request-flow
title: Inbound request path
kind: flow            # context | container | deployment | network | sequence | state | flow | concept
question: "What happens between an inbound HTTP request and a persisted record?"
direction: LR         # hint only; layout engine decides geometry
groups:
  - id: edge
    label: Edge
    members: [cdn, worker]
nodes:
  - id: cdn
    label: CDN
    role: infra       # actor | service | store | infra | external | note
    emphasis: normal  # normal | primary | muted
  - id: worker
    label: API Worker
    role: service
edges:
  - from: cdn
    to: worker
    label: cache miss
    kind: sync        # sync | async | data | dashed
```

Rules enforced by `spec.py`:

- Every edge endpoint must resolve to a declared node (no dangling edges by construction).
- Node IDs unique; group members must exist and may not overlap across groups.
- `question` is required — a diagram that cannot state the one question it answers is a diagram
  that should be split.
- Node count above the `kind`'s threshold is a validation warning that the skill must resolve by
  splitting, not by shrinking fonts.

`direction`, `emphasis`, and `role` are **intent**, not geometry or literal styling. Adapters map
them to each format's idiom.

---

## 6. Format adapters

| Target | Compilation path | Geometry source |
|---|---|---|
| **mermaid** | spec → mermaid text | mermaid's own renderer |
| **drawio** | spec → Graphviz `dot` positions → owned mxGraph XML emitter (roles/emphasis mapped to styles; `search_shapes` for branded icons) | Graphviz |
| **excalidraw** | spec → Graphviz `dot` positions *and edge splines* → `.excalidraw` JSON emitter | Graphviz |

Excalidraw and drawio are the owned emitters — Excalidraw because no upstream converter
exists, drawio because the 2026-08-16 probe retired the planned `@drawio/mcp` conversion path.
Their positions still come from Graphviz — D3 holds for all three formats.

### Format selection rubric (lives in `_shared/references/format-selection.md`)

- **Mermaid** — default for anything embedded in repo docs, reviewed in PRs, or under ~15 nodes.
  Renders natively on GitHub/Obsidian/artifacts, diffs cleanly, costs least.
- **draw.io** — detailed system architecture, branded cloud/network icons, multi-page drill-down,
  anything a human will later open and hand-edit.
- **Excalidraw** — concept sketches, teaching diagrams, whiteboard-feel explanations where
  deliberate informality signals "this is a model, not a spec".

---

## 7. The quality loop

```
emit → render (svg + png) → lint → agent reads the PNG → fix → re-render
                              ↑______________________________|   max 2 rounds
```

**`designcore lint` (deterministic, no model):**

- structural — dangling edges, duplicate IDs, orphan nodes, broken group membership
- geometry — node overlap, off-canvas content, label clipping/truncation, edge-crossing density
- density — node/edge counts above genre threshold → "split this diagram"

**Vision pass (model, bounded):** the agent reads the rendered PNG and judges only what the
linter cannot name — visual hierarchy, grouping, whether the eye finds the entry point, whether
the diagram answers its stated `question` at a glance. Two rounds maximum; if it is still wrong,
the skill reports the problem rather than looping.

**D7 in practice:** if a render backend is unavailable, the run fails with the specific missing
dependency and the install command. It never reports a diagram as complete.

---

## 8. On-disk contract

In the **target** project (not in DesignCore):

```
docs/
├── architecture.md               # embeds ../diagrams/out/system-context.svg
└── diagrams/
    ├── diagrams.yaml
    ├── src/
    │   ├── system-context.spec.yaml    # the graph spec (§5) — authored
    │   ├── system-context.drawio       # compiled source — editable by hand
    │   ├── request-flow.spec.yaml
    │   └── request-flow.mmd
    └── out/
        ├── drawio/system-context.svg / .png
        └── mermaid/request-flow.svg / .png
```

Renders are namespaced by format (`out/<format>/`). Every renderer names its output from the
source stem, which is the diagram id in all three formats, so a shared `out/` made a second
format silently overwrite the first (plan amendment A13).

`diagrams.yaml`:

```yaml
version: 1
diagrams:
  - id: system-context
    title: System context
    kind: context
    format: drawio
    question: "Which external actors and systems does the platform talk to?"
    spec: src/system-context.spec.yaml
    source: src/system-context.drawio
    rendered: [out/drawio/system-context.svg, out/drawio/system-context.png]
    embedded_in: [../architecture.md]
    generated_by: designcore
    generated_at: 2026-08-16
```

**Ownership rule:** the `.spec.yaml` is the source of truth; the compiled `.drawio` / `.mmd` /
`.excalidraw` is a build product that `designcore render` overwrites. A human who hand-edits the
compiled file must either fold the change back into the spec or mark the diagram
`hand_owned: true` in the manifest, which makes `render` refuse to overwrite it. Without this
rule, re-rendering silently destroys manual work.

`question` and `kind` are the fields that make regeneration possible without re-deriving intent —
they are why the manifest exists at all.

---

## 9. CLI surface

| Command | Behavior |
|---|---|
| `designcore new <id> --kind <k>` | Scaffold a spec file. No `--format`: a spec is format-agnostic and no entry exists yet (A17). Format is chosen at render time, defaults to `excalidraw`, and sticks (A23). |
| `designcore render <id\|--all>` | Compile spec → source → svg + png; update manifest. |
| `designcore lint <id\|--all>` | Structural + geometry + density checks; non-zero exit on failure. |
| `designcore check` | Manifest integrity: referenced files exist, embeds resolve, rendered outputs are newer than sources. |
| `designcore doctor` | Report which render backends are installed and which are missing, with install commands. |

---

## 10. Skill bundles

Each purpose skill carries: its genre's notation discipline, decomposition rules, the format
rubric pointer, and the pipeline contract (spec → render → lint → vision → manifest). Format
mechanics are read on demand from `_shared/references/`, never duplicated.

- **`architecture-diagram`** — C4-style context/container, deployment, network topology. Discipline:
  one altitude per diagram; never mix "what talks to what" with "how it is deployed"; name the
  boundary explicitly.
- **`flow-diagram`** — sequence, state, data flow, BPMN-lite. Discipline: time flows one direction;
  every branch has an exit; error paths shown or explicitly declared out of scope.
- **`concept-sketch`** — freeform explanatory sketches. Discipline: annotation over precision;
  informality signals "mental model, not spec".

All three enforce: **one diagram answers one question.** A spec whose `question` needs the word
"and" is a decomposition signal.

---

## 11. Testing

- **Golden-file tests per adapter** — spec → expected mermaid text / mxGraph XML / excalidraw JSON.
- **Lint unit tests** — deliberately broken fixtures (overlapping nodes, dangling edge, clipped
  label, 40-node graph) each asserting the specific expected finding.
- **Spec validation tests** — dangling endpoints, duplicate IDs, overlapping groups, missing
  `question`.
- **Manifest round-trip** — write, read, `check` on a synthetic project tree.
- **`doctor` degradation** — each backend stubbed missing; asserts loud failure, never silent pass.

No test asserts a diagram "looks nice". That judgment belongs to the vision pass, and pretending
to automate it would be false assurance.

---

## 12. Out of scope for v1

Deferred deliberately; none of these require rework to add later.

- Code / Terraform / Kubernetes / SQL extractors (auto-diagram from a codebase)
- C4 multi-page drill-down documents
- Build-up animations and executive-view compression
- Staleness detection (diagram-depicts-code hashing, CI drift checks)
- A DesignCore-owned shape index — `search_shapes` is delegated to `@drawio/mcp`
- Non-diagram design skills (the rest of DesignCore's eventual family)

---

## 13. Risks

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | ~~`drawio` snap CLI headless export may require `xvfb`~~ **Retired 2026-08-16** (probe: `docs/plans/2026-08-16-render-backend-findings.md` §1) | — | Export works: `xvfb-run -a drawio -x -f png -o out.png in.drawio` (plain works when `DISPLAY` is set; `--no-sandbox` not needed — the snap injects it). Hard constraint discovered: the strictly-confined snap cannot read `/tmp`; input/output paths must live under `$HOME`. `render/drawio.py` must honor this. |
| R2 | ~~No proven `.excalidraw` → SVG/PNG renderer~~ **Retired 2026-08-16** (probe: findings §3) | — | `@excalidraw/utils` `exportToSvg` works in Node **with a jsdom DOM shim** (window/document/navigator/devicePixelRatio/location/rAF/FontFace installed before a dynamic import). Plain Node fails at import time (`window is not defined`). Task 11 keeps render+vision via this shim. **Text-element rendering verified 2026-08-17 (Task 9):** all labels render as real `<text>`; the stubbed fonts only drop the embedded font-face CSS, with a non-fatal warning. The dependency must be pinned to the exact prerelease `0.1.3-test32` (plan amendment A11). |
| R3 | `mmdc` and Graphviz `dot` not installed on this machine | Nothing renders | **Resolved 2026-08-16 without sudo:** `mmdc` via `npm install -g` (nvm user prefix); graphviz via local-extract (`apt-get download` + `dpkg -x` into `~/.local/share/designcore/graphviz/rootfs`, wrapper at `~/.local/bin/dot` setting `LD_LIBRARY_PATH`/`GVBINDIR`, `dot -c` once) — **not** via `sudo apt install` as doctor's hint implies. All four backends report `ok`. Method recorded in findings §0. |
| R4 | `@drawio/mcp` desktop-Electron path upstream-broken (CSP) — **amended 2026-08-16:** probing (findings §2) shows the stdio server is the *only* invocation surface, and `open_drawio_mermaid` opens a browser editor URL rather than returning mxGraph XML | The mermaid→mxGraph conversion path assumed in §6 (drawio row) does not exist headlessly | **Resolved 2026-08-16:** the conversion path is retired; `emit/drawio.py` is an owned emitter driven by Graphviz placements (§6 drawio row; plan "Execution amendments", A1). `search_shapes` / multi-page tools remain usable as documented. |
| R5 | Dependency on upstream `@drawio/mcp` tool names/shapes — **amended 2026-08-16:** confirmed parameter shape differs from expectation (`content`, not `mermaid`) | Breakage on upstream change; conversion itself unproven (see R4) | **Resolved 2026-08-16 with R4:** no conversion dependency remains — the owned emitter calls no `@drawio/mcp` conversion tool. Any future optional use (`search_shapes`, multi-page tools) stays isolated in `emit/drawio.py`; golden tests pin the expected contract. |

---

## 14. Open questions

None blocking. R1 and R2 were answered empirically on 2026-08-16 (both retired — see the risk
table and `docs/plans/2026-08-16-render-backend-findings.md`). R4's headless
mermaid→mxGraph question was resolved the same day by decision: the conversion path is
retired and the drawio emitter is owned and Graphviz-driven (§6; plan "Execution
amendments", A1).
