# DesignCore v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build DesignCore v1 — a Python package plus three agent skills that produce verified draw.io / Mermaid / Excalidraw diagrams for documentation, where the model never places coordinates and no diagram is complete until it has rendered.

**Architecture:** A `.spec.yaml` graph spec (nodes, edges, groups — no geometry) is the source of truth. Adapters compile it to Mermaid text, mxGraph XML (owned emitter, positions from Graphviz), or Excalidraw JSON (positions from Graphviz). Every compile is followed by render → deterministic lint → bounded model vision check. Three purpose-named skills (`architecture-diagram`, `flow-diagram`, `concept-sketch`) carry the judgment layer on top.

**Tech Stack:** Python 3.11+, uv, pytest, PyYAML, argparse. External binaries: `mmdc` (mermaid-cli), `dot` (Graphviz), `drawio` (snap CLI), Node for the Excalidraw SVG export helper.

**Spec:** `docs/plans/2026-08-16-designcore-design.md` — read it before starting. This plan implements it; the spec holds the rationale.

## Global Constraints

- Python `>=3.11`. Package name `designcore`, layout `src/designcore/`, managed with `uv` (matches GearCore/DevCore house style).
- Runtime dependencies: `PyYAML` only. Everything else is an external binary invoked through `subprocess`.
- **The model never writes x/y.** No code path may accept coordinates from a spec file. Geometry comes from Graphviz or from the upstream renderer, always.
- **No diagram is complete without a successful render.** A missing backend raises `BackendMissing` with the exact install command. Never degrade silently.
- Tests must not require network access or the external binaries. Every subprocess boundary is dependency-injected or monkeypatched.
- Diagram artifacts live in the *target* project at `docs/diagrams/{diagrams.yaml,src/,out/}`, never inside DesignCore.
- Severity vocabulary is exactly `"error"` and `"warning"`. Finding codes are `UPPER_SNAKE`.
- Skill bundles follow `GearCore/SKILL_SCHEMA.md`: `SKILL.md` required, `manifest.json` optional.
- Commit after every task with a conventional-commit message.

---

## Execution amendments (2026-08-16, post-Task-2 gate)

The Task 2 probe (`docs/plans/2026-08-16-render-backend-findings.md`) disproved the design's
assumption that `@drawio/mcp` converts Mermaid→mxGraph XML headlessly. The user has decided:
the drawio emit path is an **owned emitter** — spec → Graphviz placements → DesignCore-written
mxGraph XML, mirroring the Excalidraw emitter — rendered via the proven `drawio` CLI. The
following amendments are **binding** and supersede the named task steps below.

- **A1 (supersedes Task 10 design):** `emit/drawio.py` is an OWNED emitter:
  `emit_drawio(spec: DiagramSpec, placements: dict[str, Placement], groups: dict[str, Placement] | None = None) -> str`.
  It emits `<mxfile><diagram><mxGraphModel><root>` XML: one vertex `mxCell` per node with
  absolute geometry from `placements` (never from the spec), one edge `mxCell` per edge
  (`edge="1"`, `source`/`target`, `edgeStyle=orthogonalEdgeStyle`, label via `value`), and one
  container `mxCell` per group (bounds from `groups`). Role/emphasis map to style strings
  reusing the plan's `ROLE_STYLE`/`EMPHASIS_STYLE` tables. The `Converter` alias,
  `mcp_converter`, and the restyle-after-conversion design are DELETED. Tests become
  golden-XML tests (parseable, correct cells/geometry/styles) plus a real render through the
  drawio CLI from a path under `$HOME`.
- **A2 (extends Task 7):** `layout.py` also provides
  `layout_groups(spec, run=subprocess.run, which=shutil.which) -> dict[str, Placement]`
  returning each group's bounding box (from Graphviz cluster `bb`, converted to top-left
  pixels like node placements), plus a unit test using the Task 7 FAKE_JSON fixture's
  `cluster_g` entry.
- **A3 (supersedes parts of Task 11):** `render/drawio.py` prefixes the export command with
  `xvfb-run -a` when `DISPLAY` is unset, and raises a `RenderError` explaining snap
  confinement if source/output paths are under `/tmp`. `render/excalidraw.py` IS
  implementable: a Node helper (in `src/designcore/render/js/` with its own `package.json`
  depending on `@excalidraw/utils` and `jsdom`) applies the jsdom shim from the findings doc
  §3 (shims BEFORE the dynamic import), converts `.excalidraw` JSON → SVG; PNG comes from
  headless Chrome (`google-chrome --headless=new --screenshot`) rasterizing that SVG. Missing
  node_modules or Chrome → `BackendMissing` with the exact install command. The lint-only
  fallback module in Task 11 Step 4 is NOT used.

  The `/tmp` guard stands. Task 11 Step 1's tests are amended accordingly: the BackendMissing
  test is unchanged (the backend check precedes the path guard); the success-path test
  (`test_drawio_renders_svg_and_png`) and the RenderError test must NOT use pytest's
  `tmp_path` (which lives under `/tmp`); they create scratch dirs under
  `Path.home() / '.cache' / 'designcore-tests'` with unique names and clean up afterwards.
  Add two new tests: (i) a source path under `/tmp` raises `RenderError` mentioning snap
  confinement; (ii) with `DISPLAY` removed from the environment, the issued command is
  prefixed `xvfb-run -a` (assert via the injected fake `run` capturing its `cmd`).

  A3 also amends Task 1's shipped `doctor.py`: the `node` backend's purpose string becomes
  'Run the Excalidraw SVG export helper (jsdom + @excalidraw/utils)'. Task 11 makes that
  one-line edit; no doctor test asserts on purpose strings, so nothing else changes.
- **A4 (amends Task 13):** `Deps` gains
  `layout_groups: Callable[[DiagramSpec], dict[str, Placement]]`; the drawio branch of
  `_source_text` calls `emit_drawio(spec, deps.layout(spec), deps.layout_groups(spec))`.
  Pipeline tests' fake deps supply both (groups may return `{}`).

  `Deps` LOSES the `convert` field entirely: delete `convert: Callable[[str], str]` from the
  dataclass, `convert=mcp_converter()` from `Deps.default()`, and `mcp_converter` from the
  pipeline's imports (`from designcore.emit.drawio import emit_drawio` only). The Task 13
  Step 1 test fakes drop the `convert=lambda ...` kwargs. Nothing named `mcp_converter` or
  `Converter` survives anywhere in the package.
- **A5:** Task 10 Step 5 and Task 11 Step 6 verification paths move from `/tmp/dc-probe` to
  `~/dc-probe` (snap confinement).
- **A6 (amends Task 15):** Task 15 Step 4's `drawio.md` brief is corrected: layout comes
  from Graphviz and edge routing from the owned emitter's `orthogonalEdgeStyle` declaration
  (NOT from @drawio/mcp upstream); `@drawio/mcp`'s `search_shapes` remains optionally
  available for branded icons; hand-edits to a compiled `.drawio` require
  `hand_owned: true` in the manifest.

## Execution amendments (2026-08-17, during Task 6)

- **A7 (amends Task 6, informs Task 11):** Task 6 Step 4's `render_mermaid` is amended: mmdc
  must be invoked with `-p <puppeteer config>`. The bundled Chromium cannot start on this
  machine — `kernel.apparmor_restrict_unprivileged_userns=1` and no sudo — and aborts with
  "No usable sandbox!" before writing anything, so the task's Step 6 verification failed as
  originally specified.

  `render/mermaid.py` gains `puppeteer_config(which)`: it prefers a system browser
  (`google-chrome`, `chromium`, `chromium-browser`) passed as `executablePath`, which keeps
  the Chromium sandbox **on** because those builds ship a setuid helper and an AppArmor
  profile; it falls back to `{"args": ["--no-sandbox", ...]}` only when no system browser
  exists. The config is written to a temp file and removed after rendering. User-approved
  2026-08-17. Evidence: `docs/plans/2026-08-16-render-backend-findings.md` §3b.

  Task 11's Chrome PNG rasterization (R2) must use the system `/usr/bin/google-chrome` for
  the same reason, not a puppeteer-bundled Chromium.

  This also corrects a Task 2 gap: `doctor` proves a backend is **on PATH**, never that it can
  render. Task 14's end-to-end verification is the first place that distinction is enforced.

## Execution amendments (2026-08-17, during Task 7)

- **A8 (fixes Task 7):** Task 7 Step 3's `to_dot` interpolates labels and ids into DOT
  double-quoted strings without escaping. `spec.py` places no charset restriction on a label,
  and `emit/mermaid.py` escapes quotes, so a spec that renders correctly as Mermaid killed
  every layout-dependent format with `syntax error in line 4 near '"'`. Since Tasks 9, 10 and
  11 all take their geometry from `layout_spec`, the blast radius was drawio *and* Excalidraw.

  `layout.py` gains `_quote()` — backslash first, then double quote — applied to node ids,
  node labels, group labels, and edge endpoints. Verified against real Graphviz: a spec with
  labels `the "Store"` and `C:\path` previously raised `RenderError` and now lays out.

  Reviewer's note: this is the same class of defect as an unescaped label in any other
  emitter. Task 9's Excalidraw emitter and Task 10's mxGraph emitter write labels into JSON
  and XML respectively; both need their own escaping check, and XML needs `&`, `<`, `>` as
  well. Do not assume `_quote` covers them — it is DOT-specific.

## Execution amendments (2026-08-17, during Task 8)

- **A9 (fixes Task 8):** Task 8 Step 3's `check_svg_bounds` compares raw `x`/`y` attributes
  against the root `viewBox`, ignoring SVG transforms. Every shape mmdc emits sits inside a
  `<g transform="translate(...)">` and is centred on that origin, so its local `x` is always
  negative — the check returned `CLIPPED_CONTENT` (severity **error**) for 100% of correct
  mermaid renders. Under Task 13's pipeline that would have failed every diagram. It also
  scanned only `<rect>`, while mermaid puts label text in `foreignObject` (the Task 6 probe
  output has 3 `foreignObject` and 0 `<text>`), so it was blind to the truncated labels it
  exists to catch.

  `lint/geometry.py` now accumulates an affine transform (`translate`, `scale`, `matrix`,
  `rotate`) down the tree and tests each element's four transformed corners against the
  viewBox, with a 0.5px epsilon for rounding. `foreignObject` and `image` are checked
  alongside `rect`. An unsupported transform (e.g. `skewX`) skips that subtree rather than
  producing a fictional bound. User-approved 2026-08-17.

  Verified on real mmdc output: the two Task 6 SVGs report clean, and the same content with
  a deliberately shrunk viewBox still reports `CLIPPED_CONTENT`.

  Reviewer's note: this is the second plan defect in a row (with A8) that only real rendered
  input exposed, and both were invisible to the brief's own unit tests because those tests
  used hand-written fixtures. Task 14's end-to-end verification should be treated as
  load-bearing, not a formality.

## Execution amendments (2026-08-17, during Task 10)

- **A10 (extends A8 to the drawio emitter):** `emit/drawio.py` builds its document with
  `ElementTree`, so XML escaping is correct by construction. That is necessary but not
  sufficient: every cell we emit carries `html=1`, so draw.io parses the *value* as HTML.
  A real CLI render of the label `A & B <fast>` produced well-formed XML and a picture
  reading `A & B` -- `<fast>` was silently swallowed as an unknown HTML tag.

  Labels are therefore HTML-escaped (`_label()`) before ElementTree escapes them for XML,
  so the file holds `&amp;lt;fast&amp;gt;` and draw.io renders a literal `<fast>`. Verified
  by re-rendering through `xvfb-run -a drawio -x`.

  Note for reviewers: this is a *third* distinct escaping context (DOT in A8, HTML-in-XML
  here, and JSON in Task 9, which needed nothing because `json.dumps` handles it). The
  general rule is that escaping must match the consumer, not the file format.

## Execution amendments (2026-08-17, during Task 11)

- **A11 (pins the Excalidraw helper's dependency):** `@excalidraw/utils` must be pinned to
  the **exact** version `0.1.3-test32`. The Task 2 findings recorded the install as
  `npm install @excalidraw/utils jsdom`, which at the time resolved to that prerelease. A
  caret range does not match prereleases, so `^0.1.2` silently installs the latest *stable*
  0.1.2 — which ships `dist/excalidraw-utils.min.js` and throws under the jsdom shim, while
  0.1.3-test32 ships `dist/prod/index.js` and works. The first real render of the shipped
  helper failed for exactly this reason.

  `src/designcore/render/js/package.json` therefore pins the exact version and explains why
  inline, and `package-lock.json` is committed. Depending on a prerelease is a known
  fragility: if it is ever unpublished, `render_excalidraw` fails closed with
  `BackendMissing`/`RenderError` rather than producing an unverified diagram, which is the
  behaviour the global constraints require.

- **A12 (improves A3's rasterization step):** the Chrome screenshot is passed
  `--window-size` derived from the SVG's own `width`/`height` (falling back to its
  `viewBox`, then 1200x800). Without it Chrome uses its default viewport and a small diagram
  becomes a mostly-empty 800x600 PNG — dead weight in Task 14's vision pass. Verified: the
  same scene went from a blank-padded default to a tight 364x58.

---

### Task 1: Repository scaffold and `designcore doctor`

**Files:**
- Create: `pyproject.toml`
- Create: `src/designcore/__init__.py`
- Create: `src/designcore/doctor.py`
- Create: `src/designcore/cli.py`
- Test: `tests/test_doctor.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `designcore.doctor.Backend(name, command, purpose, install_hint)`, `designcore.doctor.BackendStatus(backend, available, path)`, `designcore.doctor.check_backends(which=shutil.which) -> list[BackendStatus]`, `designcore.doctor.BACKENDS: tuple[Backend, ...]`, `designcore.cli.main(argv=None) -> int`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "designcore"
version = "0.1.0"
description = "Verified diagrams for documentation: draw.io, Mermaid, Excalidraw."
requires-python = ">=3.11"
dependencies = ["PyYAML>=6.0"]

[project.scripts]
designcore = "designcore.cli:main"

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/designcore"]
```

- [ ] **Step 2: Create the package marker**

Create `src/designcore/__init__.py` containing exactly:

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Write the failing test**

Create `tests/test_doctor.py`:

```python
from designcore.doctor import BACKENDS, check_backends


def test_reports_available_backend_with_its_path():
    statuses = check_backends(which=lambda cmd: f"/usr/bin/{cmd}")
    assert all(s.available for s in statuses)
    assert len(statuses) == len(BACKENDS)


def test_reports_missing_backend_with_install_hint():
    statuses = check_backends(which=lambda cmd: None)
    missing = [s for s in statuses if not s.available]
    assert len(missing) == len(BACKENDS)
    for status in missing:
        assert status.path is None
        assert status.backend.install_hint


def test_covers_the_three_render_backends():
    names = {b.name for b in BACKENDS}
    assert {"mermaid", "graphviz", "drawio"} <= names
```

- [ ] **Step 4: Run it to make sure it fails**

Run: `uv run pytest tests/test_doctor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.doctor'`

- [ ] **Step 5: Implement `doctor.py`**

```python
"""Report which external render backends are installed."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Backend:
    name: str
    command: str
    purpose: str
    install_hint: str


@dataclass(frozen=True)
class BackendStatus:
    backend: Backend
    available: bool
    path: str | None


BACKENDS: tuple[Backend, ...] = (
    Backend(
        name="mermaid",
        command="mmdc",
        purpose="Render Mermaid sources to SVG and PNG",
        install_hint="npm install -g @mermaid-js/mermaid-cli",
    ),
    Backend(
        name="graphviz",
        command="dot",
        purpose="Compute node geometry for Excalidraw diagrams",
        install_hint="sudo apt install graphviz",
    ),
    Backend(
        name="drawio",
        command="drawio",
        purpose="Export .drawio files to SVG and PNG",
        install_hint="sudo snap install drawio",
    ),
    Backend(
        name="node",
        command="node",
        purpose="Run @drawio/mcp for Mermaid to mxGraph XML conversion",
        install_hint="install Node.js 20+ (nvm install --lts)",
    ),
)


def check_backends(which: Callable[[str], str | None] = shutil.which) -> list[BackendStatus]:
    """Probe each backend, returning availability without raising."""
    statuses = []
    for backend in BACKENDS:
        path = which(backend.command)
        statuses.append(BackendStatus(backend=backend, available=path is not None, path=path))
    return statuses
```

- [ ] **Step 6: Implement a minimal `cli.py` exposing `doctor`**

```python
"""designcore command line entry point."""

from __future__ import annotations

import argparse
import sys

from designcore.doctor import check_backends


def _cmd_doctor(_args: argparse.Namespace) -> int:
    statuses = check_backends()
    missing = 0
    for status in statuses:
        if status.available:
            print(f"  ok       {status.backend.name:<10} {status.path}")
        else:
            missing += 1
            print(f"  MISSING  {status.backend.name:<10} {status.backend.purpose}")
            print(f"           install: {status.backend.install_hint}")
    if missing:
        print(f"\n{missing} backend(s) missing. Diagrams cannot be verified without them.")
    return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="designcore")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="Report render backend availability")
    doctor.set_defaults(func=_cmd_doctor)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_doctor.py -v`
Expected: 3 passed

- [ ] **Step 8: Verify the CLI runs**

Run: `uv run designcore doctor`
Expected: a status line per backend. On this machine `mmdc` and `dot` are expected MISSING; that is correct behavior, not a failure of this task.

- [ ] **Step 9: Commit**

```bash
git init
git add pyproject.toml uv.lock src/designcore/__init__.py src/designcore/doctor.py src/designcore/cli.py tests/test_doctor.py
git commit -m "feat: scaffold designcore package with backend doctor"
```

---

### Task 2: Prove the render backends (gate task — spec risks R1 and R2)

**Files:**
- Create: `docs/plans/2026-08-16-render-backend-findings.md`
- Modify: `docs/plans/2026-08-16-designcore-design.md` (risk table only, if findings contradict it)

**Interfaces:**
- Consumes: `designcore doctor` from Task 1.
- Produces: a written decision on (a) whether `drawio` CLI export works headless and (b) which Excalidraw renderer, if any, works. Tasks 10, 11 and 14 depend on this decision.

This task is empirical, not TDD. It exists because the spec's R1 and R2 gate the entire verify loop, and discovering them in Task 14 would waste the intervening work.

- [ ] **Step 1: Install the missing backends**

```bash
sudo apt install -y graphviz
npm install -g @mermaid-js/mermaid-cli
uv run designcore doctor
```

Expected: all four backends report `ok`.

- [ ] **Step 2: Probe headless draw.io export (risk R1)**

```bash
mkdir -p /tmp/dc-probe && cd /tmp/dc-probe
cat > probe.drawio <<'EOF'
<mxfile><diagram name="p"><mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="a" value="Alpha" style="rounded=0;" vertex="1" parent="1"><mxGeometry x="20" y="20" width="120" height="60" as="geometry"/></mxCell>
<mxCell id="b" value="Beta" style="rounded=0;" vertex="1" parent="1"><mxGeometry x="220" y="20" width="120" height="60" as="geometry"/></mxCell>
<mxCell id="e" style="edgeStyle=orthogonalEdgeStyle;" edge="1" parent="1" source="a" target="b"><mxGeometry relative="1" as="geometry"/></mxCell>
</root></mxGraphModel></diagram></mxfile>
EOF
drawio -x -f png -o probe.png probe.drawio; echo "exit=$?"; ls -la probe.png
```

If it fails on a missing display, retry under xvfb:

```bash
sudo apt install -y xvfb
xvfb-run -a drawio -x -f png -o probe.png probe.drawio; echo "exit=$?"; ls -la probe.png
```

Record which invocation worked and whether `--no-sandbox` was also required.

- [ ] **Step 3: Probe Mermaid→mxGraph conversion via the official MCP**

```bash
npx -y @drawio/mcp --help
```

Record the actual invocation surface: whether it can be driven one-shot from the command line, or only as an MCP stdio server. Task 10 needs to know which.

- [ ] **Step 4: Probe an Excalidraw renderer (risk R2)**

```bash
cd /tmp/dc-probe && npm init -y >/dev/null && npm install @excalidraw/utils
cat > probe.mjs <<'EOF'
import { exportToSvg } from "@excalidraw/utils";
const elements = [{
  type: "rectangle", version: 1, versionNonce: 1, isDeleted: false,
  id: "r1", fillStyle: "solid", strokeWidth: 1, strokeStyle: "solid",
  roughness: 1, opacity: 100, angle: 0, x: 20, y: 20, strokeColor: "#1e1e1e",
  backgroundColor: "transparent", width: 120, height: 60, seed: 1, groupIds: [],
  frameId: null, roundness: null, boundElements: [], updated: 1, link: null, locked: false,
}];
const svg = await exportToSvg({ elements, appState: { exportBackground: true }, files: null });
console.log(svg.outerHTML.slice(0, 200));
EOF
node probe.mjs; echo "exit=$?"
```

- [ ] **Step 5: Write the findings document**

Create `docs/plans/2026-08-16-render-backend-findings.md` recording, for each of the three probes: the exact working command, the exit code, and a one-line verdict (`works` / `works with <workaround>` / `unavailable`). For any probe that failed, state the chosen fallback:

- draw.io export unavailable → Task 11 renders the emitted XML through an alternative exporter; record which.
- Excalidraw render unavailable → Task 11's render_excalidraw is reduced to lint-only (superseded: the probe succeeded; see amendment A3), and the `concept-sketch` skill must state that limitation explicitly in its SKILL.md rather than implying verification.

- [ ] **Step 6: Reconcile the design doc**

If a probe contradicts the design's risk table, update the R1/R2 rows in `docs/plans/2026-08-16-designcore-design.md` to state what is now known. Do not stack a second source of truth — edit the risk table in place.

- [ ] **Step 7: Commit**

```bash
git add docs/plans/
git commit -m "docs: record render backend probe findings for R1 and R2"
```

---

### Task 3: Graph spec model and validation

**Files:**
- Create: `src/designcore/spec.py`
- Test: `tests/test_spec.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Node(id, label, role, emphasis)`, `Edge(source, target, label, kind)`, `Group(id, label, members)`, `DiagramSpec(id, title, kind, question, direction, nodes, edges, groups)`, `SpecError(ValueError)`, `parse_spec(data: dict) -> DiagramSpec`, `load_spec(path: Path) -> DiagramSpec`. All collections are tuples; `DiagramSpec` is frozen.

Note the YAML uses `from`/`to` for edges (readable for authors) while the model uses `source`/`target` (`from` is a Python keyword). `parse_spec` performs that translation.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_spec.py`:

```python
import pytest

from designcore.spec import DiagramSpec, SpecError, parse_spec

VALID = {
    "id": "request-flow",
    "title": "Inbound request path",
    "kind": "flow",
    "question": "What happens between an inbound request and a persisted record?",
    "direction": "LR",
    "nodes": [
        {"id": "cdn", "label": "CDN", "role": "infra"},
        {"id": "worker", "label": "API Worker", "role": "service"},
    ],
    "edges": [{"from": "cdn", "to": "worker", "label": "cache miss"}],
    "groups": [{"id": "edge", "label": "Edge", "members": ["cdn", "worker"]}],
}


def test_parses_a_valid_spec():
    spec = parse_spec(VALID)
    assert isinstance(spec, DiagramSpec)
    assert spec.id == "request-flow"
    assert spec.nodes[0].label == "CDN"
    assert spec.edges[0].source == "cdn"
    assert spec.edges[0].target == "worker"
    assert spec.edges[0].kind == "sync"
    assert spec.groups[0].members == ("cdn", "worker")


def test_rejects_missing_question():
    data = {k: v for k, v in VALID.items() if k != "question"}
    with pytest.raises(SpecError, match="question"):
        parse_spec(data)


def test_rejects_edge_pointing_at_undeclared_node():
    data = {**VALID, "edges": [{"from": "cdn", "to": "ghost"}]}
    with pytest.raises(SpecError, match="ghost"):
        parse_spec(data)


def test_rejects_duplicate_node_ids():
    data = {**VALID, "nodes": [{"id": "cdn", "label": "A"}, {"id": "cdn", "label": "B"}]}
    with pytest.raises(SpecError, match="duplicate"):
        parse_spec(data)


def test_rejects_group_member_that_is_not_a_node():
    data = {**VALID, "groups": [{"id": "g", "label": "G", "members": ["ghost"]}]}
    with pytest.raises(SpecError, match="ghost"):
        parse_spec(data)


def test_rejects_node_in_two_groups():
    data = {
        **VALID,
        "groups": [
            {"id": "g1", "label": "One", "members": ["cdn"]},
            {"id": "g2", "label": "Two", "members": ["cdn"]},
        ],
    }
    with pytest.raises(SpecError, match="more than one group"):
        parse_spec(data)


def test_rejects_coordinates_in_the_spec():
    data = {**VALID, "nodes": [{"id": "cdn", "label": "CDN", "x": 10, "y": 20}]}
    with pytest.raises(SpecError, match="coordinates"):
        parse_spec(data)


def test_rejects_unknown_kind():
    with pytest.raises(SpecError, match="kind"):
        parse_spec({**VALID, "kind": "interpretive-dance"})
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_spec.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.spec'`

- [ ] **Step 3: Implement `spec.py`**

```python
"""The graph spec: what a diagram contains, never where anything sits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

KINDS = frozenset(
    {"context", "container", "deployment", "network", "sequence", "state", "flow", "concept"}
)
ROLES = frozenset({"actor", "service", "store", "infra", "external", "note"})
EMPHASES = frozenset({"normal", "primary", "muted"})
EDGE_KINDS = frozenset({"sync", "async", "data", "dashed"})
GEOMETRY_KEYS = frozenset({"x", "y", "width", "height", "position"})


class SpecError(ValueError):
    """A spec that cannot be compiled into a diagram."""


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    role: str = "service"
    emphasis: str = "normal"


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str = ""
    kind: str = "sync"


@dataclass(frozen=True)
class Group:
    id: str
    label: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class DiagramSpec:
    id: str
    title: str
    kind: str
    question: str
    direction: str = "TB"
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    groups: tuple[Group, ...] = ()


def _require(data: dict, field: str) -> str:
    value = data.get(field)
    if not value or not str(value).strip():
        raise SpecError(f"spec is missing required field {field!r}")
    return str(value)


def _one_of(value: str, allowed: frozenset[str], field: str) -> str:
    if value not in allowed:
        raise SpecError(f"unknown {field} {value!r}; expected one of {sorted(allowed)}")
    return value


def parse_spec(data: dict) -> DiagramSpec:
    """Build a validated DiagramSpec from raw mapping data."""
    spec_id = _require(data, "id")
    title = _require(data, "title")
    kind = _one_of(_require(data, "kind"), KINDS, "kind")
    question = _require(data, "question")

    nodes: list[Node] = []
    seen: set[str] = set()
    for raw in data.get("nodes", []):
        leaked = GEOMETRY_KEYS & set(raw)
        if leaked:
            raise SpecError(
                f"node {raw.get('id')!r} declares coordinates {sorted(leaked)}; "
                "geometry comes from the layout engine, never from the spec"
            )
        node_id = _require(raw, "id")
        if node_id in seen:
            raise SpecError(f"duplicate node id {node_id!r}")
        seen.add(node_id)
        nodes.append(
            Node(
                id=node_id,
                label=str(raw.get("label", node_id)),
                role=_one_of(str(raw.get("role", "service")), ROLES, "role"),
                emphasis=_one_of(str(raw.get("emphasis", "normal")), EMPHASES, "emphasis"),
            )
        )

    edges: list[Edge] = []
    for raw in data.get("edges", []):
        source, target = _require(raw, "from"), _require(raw, "to")
        for endpoint in (source, target):
            if endpoint not in seen:
                raise SpecError(f"edge endpoint {endpoint!r} is not a declared node")
        edges.append(
            Edge(
                source=source,
                target=target,
                label=str(raw.get("label", "")),
                kind=_one_of(str(raw.get("kind", "sync")), EDGE_KINDS, "edge kind"),
            )
        )

    groups: list[Group] = []
    claimed: set[str] = set()
    for raw in data.get("groups", []):
        members = tuple(str(m) for m in raw.get("members", []))
        for member in members:
            if member not in seen:
                raise SpecError(f"group member {member!r} is not a declared node")
            if member in claimed:
                raise SpecError(f"node {member!r} belongs to more than one group")
            claimed.add(member)
        groups.append(Group(id=_require(raw, "id"), label=str(raw.get("label", "")), members=members))

    return DiagramSpec(
        id=spec_id,
        title=title,
        kind=kind,
        question=question,
        direction=str(data.get("direction", "TB")),
        nodes=tuple(nodes),
        edges=tuple(edges),
        groups=tuple(groups),
    )


def load_spec(path: Path) -> DiagramSpec:
    """Read and validate a .spec.yaml file."""
    with Path(path).open(encoding="utf-8") as handle:
        return parse_spec(yaml.safe_load(handle) or {})
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_spec.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/designcore/spec.py tests/test_spec.py
git commit -m "feat: add graph spec model with coordinate-free validation"
```

---

### Task 4: Structural and density lint

**Files:**
- Create: `src/designcore/lint/__init__.py`
- Create: `src/designcore/lint/structural.py`
- Create: `src/designcore/lint/density.py`
- Test: `tests/test_lint_spec.py`

**Interfaces:**
- Consumes: `designcore.spec.DiagramSpec`.
- Produces: `designcore.lint.Finding(code, severity, message, subject)`, `designcore.lint.structural.check_structure(spec) -> list[Finding]`, `designcore.lint.density.check_density(spec) -> list[Finding]`, `designcore.lint.density.THRESHOLDS: dict[str, int]`.

`spec.py` rejects malformed specs at parse time; these checks catch what is *valid but bad* — isolated nodes, empty groups, graphs too dense to read.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lint_spec.py`:

```python
from designcore.lint import Finding
from designcore.lint.density import THRESHOLDS, check_density
from designcore.lint.structural import check_structure
from designcore.spec import DiagramSpec, Edge, Group, Node


def _spec(**overrides) -> DiagramSpec:
    base = dict(
        id="d", title="T", kind="flow", question="Q?",
        nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
        edges=(Edge(source="a", target="b"),),
        groups=(),
    )
    return DiagramSpec(**{**base, "direction": "TB", **overrides})


def test_clean_spec_has_no_structural_findings():
    assert check_structure(_spec()) == []


def test_flags_isolated_node():
    spec = _spec(nodes=(Node(id="a", label="A"), Node(id="b", label="B"), Node(id="c", label="C")))
    findings = check_structure(spec)
    assert [f.code for f in findings] == ["ISOLATED_NODE"]
    assert findings[0].subject == "c"
    assert findings[0].severity == "warning"


def test_flags_empty_group():
    spec = _spec(groups=(Group(id="g", label="G", members=()),))
    assert [f.code for f in check_structure(spec)] == ["EMPTY_GROUP"]


def test_flags_self_loop():
    spec = _spec(edges=(Edge(source="a", target="a"),))
    codes = {f.code for f in check_structure(spec)}
    assert "SELF_LOOP" in codes


def test_density_under_threshold_is_clean():
    assert check_density(_spec()) == []


def test_density_over_threshold_says_split():
    nodes = tuple(Node(id=f"n{i}", label=f"N{i}") for i in range(THRESHOLDS["flow"] + 1))
    edges = tuple(Edge(source="n0", target=f"n{i}") for i in range(1, len(nodes)))
    finding = check_density(_spec(nodes=nodes, edges=edges))[0]
    assert finding.code == "TOO_DENSE"
    assert finding.severity == "error"
    assert "split" in finding.message.lower()


def test_findings_are_comparable():
    a = Finding(code="X", severity="warning", message="m", subject="s")
    assert a == Finding(code="X", severity="warning", message="m", subject="s")
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_lint_spec.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.lint'`

- [ ] **Step 3: Implement `lint/__init__.py`**

```python
"""Deterministic diagram checks. Nothing here calls a model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str  # "error" | "warning"
    message: str
    subject: str = ""


def has_errors(findings: list[Finding]) -> bool:
    return any(f.severity == "error" for f in findings)
```

- [ ] **Step 4: Implement `lint/structural.py`**

```python
"""Checks on graph shape: things that are valid but unreadable."""

from __future__ import annotations

from designcore.lint import Finding
from designcore.spec import DiagramSpec


def check_structure(spec: DiagramSpec) -> list[Finding]:
    findings: list[Finding] = []
    connected = {e.source for e in spec.edges} | {e.target for e in spec.edges}

    for node in spec.nodes:
        if node.id not in connected:
            findings.append(
                Finding(
                    code="ISOLATED_NODE",
                    severity="warning",
                    message=f"node {node.label!r} has no edges; is it part of this diagram?",
                    subject=node.id,
                )
            )

    for edge in spec.edges:
        if edge.source == edge.target:
            findings.append(
                Finding(
                    code="SELF_LOOP",
                    severity="warning",
                    message=f"edge on {edge.source!r} points at itself",
                    subject=edge.source,
                )
            )

    for group in spec.groups:
        if not group.members:
            findings.append(
                Finding(
                    code="EMPTY_GROUP",
                    severity="warning",
                    message=f"group {group.label or group.id!r} contains no nodes",
                    subject=group.id,
                )
            )

    return findings
```

- [ ] **Step 5: Implement `lint/density.py`**

```python
"""Density checks: a diagram that answers one question stays small."""

from __future__ import annotations

from designcore.lint import Finding
from designcore.spec import DiagramSpec

THRESHOLDS: dict[str, int] = {
    "context": 12,
    "container": 16,
    "deployment": 16,
    "network": 20,
    "sequence": 10,
    "state": 14,
    "flow": 18,
    "concept": 12,
}
DEFAULT_THRESHOLD = 16


def check_density(spec: DiagramSpec) -> list[Finding]:
    limit = THRESHOLDS.get(spec.kind, DEFAULT_THRESHOLD)
    if len(spec.nodes) <= limit:
        return []
    return [
        Finding(
            code="TOO_DENSE",
            severity="error",
            message=(
                f"{len(spec.nodes)} nodes exceeds the {limit}-node limit for kind {spec.kind!r}; "
                "split this into diagrams that each answer one question"
            ),
            subject=spec.id,
        )
    ]
```

- [ ] **Step 6: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_lint_spec.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add src/designcore/lint tests/test_lint_spec.py
git commit -m "feat: add structural and density lint over the graph spec"
```

---

### Task 5: Mermaid emitter

**Files:**
- Create: `src/designcore/emit/__init__.py`
- Create: `src/designcore/emit/mermaid.py`
- Test: `tests/test_emit_mermaid.py`

**Interfaces:**
- Consumes: `designcore.spec.DiagramSpec`.
- Produces: `designcore.emit.mermaid.emit_mermaid(spec: DiagramSpec) -> str`.

Mermaid is a delivery format in its own right, so its output must be correct before anything downstream. (The drawio emitter is owned and Graphviz-driven — Task 10, per amendment A1 — and does not convert from mermaid.)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_emit_mermaid.py`:

```python
from designcore.emit.mermaid import emit_mermaid
from designcore.spec import DiagramSpec, Edge, Group, Node


def _spec(**overrides) -> DiagramSpec:
    base = dict(
        id="d", title="T", kind="flow", question="Q?", direction="LR",
        nodes=(Node(id="cdn", label="CDN", role="infra"),
               Node(id="worker", label="API Worker", role="service", emphasis="primary")),
        edges=(Edge(source="cdn", target="worker", label="cache miss"),),
        groups=(),
    )
    return DiagramSpec(**{**base, **overrides})


def test_emits_flowchart_header_with_direction():
    assert emit_mermaid(_spec()).splitlines()[0] == "flowchart LR"


def test_emits_nodes_and_labelled_edge():
    out = emit_mermaid(_spec())
    assert 'cdn["CDN"]' in out
    assert 'worker["API Worker"]' in out
    assert "cdn -->|cache miss| worker" in out


def test_unlabelled_edge_has_no_pipe_section():
    out = emit_mermaid(_spec(edges=(Edge(source="cdn", target="worker"),)))
    assert "cdn --> worker" in out
    assert "|" not in out


def test_async_edge_uses_dotted_arrow():
    out = emit_mermaid(_spec(edges=(Edge(source="cdn", target="worker", kind="async"),)))
    assert "cdn -.-> worker" in out


def test_groups_become_subgraphs():
    out = emit_mermaid(_spec(groups=(Group(id="edge", label="Edge", members=("cdn",)),)))
    assert 'subgraph edge["Edge"]' in out
    assert out.count("end") == 1


def test_emphasis_becomes_a_class_directive():
    out = emit_mermaid(_spec())
    assert "class worker primary" in out


def test_quotes_in_labels_are_escaped():
    out = emit_mermaid(_spec(nodes=(Node(id="a", label='the "edge"'),
                                    Node(id="worker", label="W"))))
    assert '&quot;edge&quot;' in out
    assert '"the "edge""' not in out


def test_output_is_deterministic():
    assert emit_mermaid(_spec()) == emit_mermaid(_spec())
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_emit_mermaid.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.emit'`

- [ ] **Step 3: Create `src/designcore/emit/__init__.py`**

```python
"""Adapters compiling a graph spec into concrete diagram formats."""
```

- [ ] **Step 4: Implement `emit/mermaid.py`**

```python
"""Compile a graph spec to Mermaid flowchart source."""

from __future__ import annotations

from designcore.spec import DiagramSpec

ARROWS = {"sync": "-->", "async": "-.->", "data": "==>", "dashed": "-.->"}


def _escape(label: str) -> str:
    return label.replace('"', "&quot;")


def emit_mermaid(spec: DiagramSpec) -> str:
    lines = [f"flowchart {spec.direction}"]
    grouped = {member for group in spec.groups for member in group.members}

    for group in spec.groups:
        lines.append(f'    subgraph {group.id}["{_escape(group.label)}"]')
        for member in group.members:
            node = next(n for n in spec.nodes if n.id == member)
            lines.append(f'        {node.id}["{_escape(node.label)}"]')
        lines.append("    end")

    for node in spec.nodes:
        if node.id not in grouped:
            lines.append(f'    {node.id}["{_escape(node.label)}"]')

    for edge in spec.edges:
        arrow = ARROWS[edge.kind]
        if edge.label:
            lines.append(f"    {edge.source} {arrow}|{_escape(edge.label)}| {edge.target}")
        else:
            lines.append(f"    {edge.source} {arrow} {edge.target}")

    for node in spec.nodes:
        if node.emphasis != "normal":
            lines.append(f"    class {node.id} {node.emphasis}")

    if any(n.emphasis != "normal" for n in spec.nodes):
        lines.append("    classDef primary stroke-width:3px")
        lines.append("    classDef muted opacity:0.55")

    return "\n".join(lines) + "\n"
```

- [ ] **Step 5: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_emit_mermaid.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add src/designcore/emit tests/test_emit_mermaid.py
git commit -m "feat: add mermaid emitter"
```

---

### Task 6: Mermaid renderer

**Files:**
- Create: `src/designcore/render/__init__.py`
- Create: `src/designcore/render/mermaid.py`
- Test: `tests/test_render_mermaid.py`

**Interfaces:**
- Consumes: nothing from earlier tasks at runtime.
- Produces: `designcore.render.BackendMissing(RuntimeError)`, `designcore.render.RenderError(RuntimeError)`, `designcore.render.mermaid.render_mermaid(source: Path, out_dir: Path, run=subprocess.run, which=shutil.which) -> list[Path]` returning `[svg_path, png_path]`.

`run` and `which` are injected so tests never touch the real `mmdc`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render_mermaid.py`:

```python
import subprocess
from pathlib import Path

import pytest

from designcore.render import BackendMissing, RenderError
from designcore.render.mermaid import render_mermaid


def _ok(cmd, **kwargs):
    Path(cmd[cmd.index("-o") + 1]).write_text("rendered", encoding="utf-8")
    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def test_raises_backend_missing_with_install_hint(tmp_path):
    src = tmp_path / "d.mmd"
    src.write_text("flowchart LR\n  a --> b\n", encoding="utf-8")
    with pytest.raises(BackendMissing, match="mermaid-cli"):
        render_mermaid(src, tmp_path / "out", run=_ok, which=lambda c: None)


def test_renders_svg_and_png(tmp_path):
    src = tmp_path / "d.mmd"
    src.write_text("flowchart LR\n  a --> b\n", encoding="utf-8")
    outputs = render_mermaid(src, tmp_path / "out", run=_ok, which=lambda c: "/usr/bin/mmdc")
    assert [p.suffix for p in outputs] == [".svg", ".png"]
    assert all(p.exists() for p in outputs)


def test_raises_render_error_on_nonzero_exit(tmp_path):
    src = tmp_path / "d.mmd"
    src.write_text("not mermaid at all", encoding="utf-8")

    def fail(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Parse error on line 1")

    with pytest.raises(RenderError, match="Parse error"):
        render_mermaid(src, tmp_path / "out", run=fail, which=lambda c: "/usr/bin/mmdc")
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_render_mermaid.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.render'`

- [ ] **Step 3: Implement `render/__init__.py`**

```python
"""Rendering: the step that proves a diagram exists as a picture."""

from __future__ import annotations


class BackendMissing(RuntimeError):
    """A required external renderer is not installed."""


class RenderError(RuntimeError):
    """The renderer ran and refused the input."""
```

- [ ] **Step 4: Implement `render/mermaid.py`**

```python
"""Render Mermaid sources with mermaid-cli."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

from designcore.render import BackendMissing, RenderError

INSTALL_HINT = "npm install -g @mermaid-js/mermaid-cli"


def render_mermaid(
    source: Path,
    out_dir: Path,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> list[Path]:
    """Render a .mmd file to SVG and PNG. Returns the written paths."""
    if which("mmdc") is None:
        raise BackendMissing(
            f"mermaid-cli (mmdc) is not installed, so this diagram cannot be verified. "
            f"Install it with: {INSTALL_HINT}"
        )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    for suffix in (".svg", ".png"):
        target = out_dir / (Path(source).stem + suffix)
        result = run(
            ["mmdc", "-i", str(source), "-o", str(target), "-b", "transparent"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RenderError(f"mmdc failed on {source}: {result.stderr.strip()}")
        outputs.append(target)
    return outputs
```

- [ ] **Step 5: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_render_mermaid.py -v`
Expected: 3 passed

- [ ] **Step 6: Verify against the real binary**

```bash
printf 'flowchart LR\n  a["A"] --> b["B"]\n' > /tmp/dc-probe/real.mmd
uv run python -c "
from pathlib import Path
from designcore.render.mermaid import render_mermaid
print(render_mermaid(Path('/tmp/dc-probe/real.mmd'), Path('/tmp/dc-probe/out')))
"
```

Expected: two paths printed, both files non-empty.

- [ ] **Step 7: Commit**

```bash
git add src/designcore/render tests/test_render_mermaid.py
git commit -m "feat: render mermaid sources to svg and png"
```

---

### Task 7: Graphviz layout

**Files:**
- Create: `src/designcore/layout.py`
- Test: `tests/test_layout.py`

**Interfaces:**
- Consumes: `designcore.spec.DiagramSpec`, `designcore.render.BackendMissing`.
- Produces: `designcore.layout.Placement(id, x, y, width, height)`, `designcore.layout.to_dot(spec) -> str`, `designcore.layout.layout_spec(spec, run=subprocess.run, which=shutil.which) -> dict[str, Placement]`.

This is the mechanism behind global constraint D3: geometry originates here, never in a spec file. Graphviz reports positions in points with the origin bottom-left; `layout_spec` converts to a top-left origin in pixels so downstream emitters need no coordinate maths.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_layout.py`:

```python
import json
import subprocess

import pytest

from designcore.layout import Placement, layout_spec, to_dot
from designcore.render import BackendMissing
from designcore.spec import DiagramSpec, Edge, Group, Node

SPEC = DiagramSpec(
    id="d", title="T", kind="flow", question="Q?", direction="LR",
    nodes=(Node(id="a", label="A"), Node(id="b", label="Beta")),
    edges=(Edge(source="a", target="b"),),
    groups=(Group(id="g", label="G", members=("a",)),),
)

FAKE_JSON = json.dumps({
    "bb": "0,0,200,100",
    "objects": [
        {"name": "a", "pos": "50,80", "width": "1.0", "height": "0.5"},
        {"name": "b", "pos": "150,80", "width": "1.5", "height": "0.5"},
        {"name": "cluster_g", "bb": "10,10,110,110"},
    ],
})


def _ok(cmd, **kwargs):
    return subprocess.CompletedProcess(cmd, 0, stdout=FAKE_JSON, stderr="")


def test_dot_source_declares_nodes_edges_and_cluster():
    dot = to_dot(SPEC)
    assert "rankdir=LR" in dot
    assert '"a" [label="A"' in dot
    assert '"a" -> "b"' in dot
    assert "subgraph cluster_g" in dot


def test_layout_returns_top_left_pixel_placements():
    placements = layout_spec(SPEC, run=_ok, which=lambda c: "/usr/bin/dot")
    assert set(placements) == {"a", "b"}
    a = placements["a"]
    assert isinstance(a, Placement)
    assert a.width == 72.0            # 1.0 inch at 72 dpi
    assert a.x == 50.0 - 72.0 / 2     # centre-based pos converted to left edge
    assert a.y == 100 - 80 - 36 / 2   # bottom-left origin flipped to top-left


def test_missing_graphviz_raises_backend_missing():
    with pytest.raises(BackendMissing, match="graphviz"):
        layout_spec(SPEC, run=_ok, which=lambda c: None)


def test_clusters_are_not_returned_as_node_placements():
    placements = layout_spec(SPEC, run=_ok, which=lambda c: "/usr/bin/dot")
    assert "cluster_g" not in placements


def test_no_two_nodes_overlap_in_returned_placements():
    placements = layout_spec(SPEC, run=_ok, which=lambda c: "/usr/bin/dot")
    a, b = placements["a"], placements["b"]
    assert a.x + a.width <= b.x or b.x + b.width <= a.x
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_layout.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.layout'`

- [ ] **Step 3: Implement `layout.py`**

```python
"""Geometry comes from Graphviz. The model never supplies coordinates."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from designcore.render import BackendMissing, RenderError
from designcore.spec import DiagramSpec

DPI = 72.0
INSTALL_HINT = "sudo apt install graphviz"


@dataclass(frozen=True)
class Placement:
    id: str
    x: float
    y: float
    width: float
    height: float


def to_dot(spec: DiagramSpec) -> str:
    rankdir = "LR" if spec.direction.upper() in {"LR", "RL"} else "TB"
    lines = [f"digraph {spec.id.replace('-', '_')} {{", f"  rankdir={rankdir};", "  node [shape=box];"]
    grouped = {m for g in spec.groups for m in g.members}

    for group in spec.groups:
        lines.append(f"  subgraph cluster_{group.id} {{")
        lines.append(f'    label="{group.label}";')
        for member in group.members:
            node = next(n for n in spec.nodes if n.id == member)
            lines.append(f'    "{node.id}" [label="{node.label}"];')
        lines.append("  }")

    for node in spec.nodes:
        if node.id not in grouped:
            lines.append(f'  "{node.id}" [label="{node.label}"];')

    for edge in spec.edges:
        lines.append(f'  "{edge.source}" -> "{edge.target}";')

    lines.append("}")
    return "\n".join(lines) + "\n"


def layout_spec(
    spec: DiagramSpec,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> dict[str, Placement]:
    """Return top-left-origin pixel placements keyed by node id."""
    if which("dot") is None:
        raise BackendMissing(
            f"graphviz (dot) is not installed, so node geometry cannot be computed. "
            f"Install it with: {INSTALL_HINT}"
        )
    result = run(["dot", "-Tjson"], input=to_dot(spec), capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderError(f"dot failed for spec {spec.id}: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    _, _, _, canvas_height = (float(v) for v in data["bb"].split(","))
    node_ids = {n.id for n in spec.nodes}

    placements: dict[str, Placement] = {}
    for obj in data.get("objects", []):
        name = obj.get("name", "")
        if name not in node_ids:
            continue  # clusters and anything else Graphviz reports
        cx, cy = (float(v) for v in obj["pos"].split(","))
        width = float(obj["width"]) * DPI
        height = float(obj["height"]) * DPI
        placements[name] = Placement(
            id=name,
            x=cx - width / 2,
            y=canvas_height - cy - height / 2,
            width=width,
            height=height,
        )
    return placements
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_layout.py -v`
Expected: 5 passed

- [ ] **Step 5: Verify against real Graphviz**

```bash
uv run python -c "
from designcore.layout import layout_spec
from designcore.spec import DiagramSpec, Node, Edge
s = DiagramSpec(id='d', title='T', kind='flow', question='Q?', direction='LR',
                nodes=(Node(id='a', label='A'), Node(id='b', label='Beta')),
                edges=(Edge(source='a', target='b'),))
for p in layout_spec(s).values(): print(p)
"
```

Expected: two `Placement` lines with non-negative, non-overlapping coordinates.

- [ ] **Step 6: Commit**

```bash
git add src/designcore/layout.py tests/test_layout.py
git commit -m "feat: compute node geometry with graphviz"
```

---

### Task 8: Geometry lint

**Files:**
- Create: `src/designcore/lint/geometry.py`
- Test: `tests/test_lint_geometry.py`

**Interfaces:**
- Consumes: `designcore.layout.Placement`, `designcore.lint.Finding`.
- Produces: `designcore.lint.geometry.check_geometry(placements: list[Placement], canvas: tuple[float, float] | None = None) -> list[Finding]`, `designcore.lint.geometry.check_svg_bounds(svg_path: Path) -> list[Finding]`.

`check_geometry` catches overlap and off-canvas content in any format that has placements. `check_svg_bounds` catches content clipped by the viewBox in a rendered SVG, which is the observable form of truncated labels.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lint_geometry.py`:

```python
from designcore.layout import Placement
from designcore.lint.geometry import check_geometry, check_svg_bounds


def test_separated_boxes_are_clean():
    boxes = [Placement("a", 0, 0, 100, 50), Placement("b", 150, 0, 100, 50)]
    assert check_geometry(boxes) == []


def test_overlapping_boxes_are_an_error():
    boxes = [Placement("a", 0, 0, 100, 50), Placement("b", 50, 10, 100, 50)]
    findings = check_geometry(boxes)
    assert [f.code for f in findings] == ["NODE_OVERLAP"]
    assert findings[0].severity == "error"
    assert "a" in findings[0].subject and "b" in findings[0].subject


def test_touching_edges_do_not_count_as_overlap():
    boxes = [Placement("a", 0, 0, 100, 50), Placement("b", 100, 0, 100, 50)]
    assert check_geometry(boxes) == []


def test_negative_coordinates_are_off_canvas():
    findings = check_geometry([Placement("a", -10, 0, 100, 50)])
    assert [f.code for f in findings] == ["OFF_CANVAS"]


def test_box_beyond_declared_canvas_is_off_canvas():
    findings = check_geometry([Placement("a", 0, 0, 100, 50)], canvas=(80, 200))
    assert [f.code for f in findings] == ["OFF_CANVAS"]


def test_svg_within_viewbox_is_clean(tmp_path):
    svg = tmp_path / "ok.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
        '<rect x="10" y="10" width="100" height="50"/></svg>',
        encoding="utf-8",
    )
    assert check_svg_bounds(svg) == []


def test_svg_content_outside_viewbox_is_clipped(tmp_path):
    svg = tmp_path / "clipped.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect x="10" y="10" width="200" height="50"/></svg>',
        encoding="utf-8",
    )
    findings = check_svg_bounds(svg)
    assert [f.code for f in findings] == ["CLIPPED_CONTENT"]
    assert findings[0].severity == "error"
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_lint_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.lint.geometry'`

- [ ] **Step 3: Implement `lint/geometry.py`**

```python
"""Geometry checks over placements and rendered SVG."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from xml.etree import ElementTree

from designcore.layout import Placement
from designcore.lint import Finding

SVG_NS = "{http://www.w3.org/2000/svg}"


def _overlaps(a: Placement, b: Placement) -> bool:
    return (
        a.x < b.x + b.width
        and b.x < a.x + a.width
        and a.y < b.y + b.height
        and b.y < a.y + a.height
    )


def check_geometry(
    placements: list[Placement], canvas: tuple[float, float] | None = None
) -> list[Finding]:
    findings: list[Finding] = []

    for a, b in combinations(placements, 2):
        if _overlaps(a, b):
            findings.append(
                Finding(
                    code="NODE_OVERLAP",
                    severity="error",
                    message=f"nodes {a.id!r} and {b.id!r} overlap",
                    subject=f"{a.id},{b.id}",
                )
            )

    for box in placements:
        outside = box.x < 0 or box.y < 0
        if canvas is not None:
            width, height = canvas
            outside = outside or box.x + box.width > width or box.y + box.height > height
        if outside:
            findings.append(
                Finding(
                    code="OFF_CANVAS",
                    severity="error",
                    message=f"node {box.id!r} falls outside the canvas",
                    subject=box.id,
                )
            )

    return findings


def check_svg_bounds(svg_path: Path) -> list[Finding]:
    """Flag rendered content that extends past the viewBox, i.e. clipped output."""
    root = ElementTree.parse(svg_path).getroot()
    view_box = root.get("viewBox")
    if not view_box:
        return []
    min_x, min_y, width, height = (float(v) for v in view_box.replace(",", " ").split())

    for rect in root.iter(f"{SVG_NS}rect"):
        try:
            x = float(rect.get("x", 0))
            y = float(rect.get("y", 0))
            w = float(rect.get("width", 0))
            h = float(rect.get("height", 0))
        except ValueError:
            continue
        if x < min_x or y < min_y or x + w > min_x + width or y + h > min_y + height:
            return [
                Finding(
                    code="CLIPPED_CONTENT",
                    severity="error",
                    message=f"rendered content extends past the viewBox in {svg_path.name}",
                    subject=svg_path.name,
                )
            ]
    return []
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_lint_geometry.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/designcore/lint/geometry.py tests/test_lint_geometry.py
git commit -m "feat: add geometry lint for overlap, off-canvas, and clipping"
```

---

### Task 9: Excalidraw emitter

**Files:**
- Create: `src/designcore/emit/excalidraw.py`
- Test: `tests/test_emit_excalidraw.py`

**Interfaces:**
- Consumes: `designcore.spec.DiagramSpec`, `designcore.layout.Placement`.
- Produces: `designcore.emit.excalidraw.emit_excalidraw(spec: DiagramSpec, placements: dict[str, Placement]) -> dict`.

This is one of two emitters DesignCore owns outright (the drawio emitter is owned too — see amendments A1/A4), because no upstream Mermaid→Excalidraw converter exists. Positions still come from Graphviz.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_emit_excalidraw.py`:

```python
import pytest

from designcore.emit.excalidraw import emit_excalidraw
from designcore.layout import Placement
from designcore.spec import DiagramSpec, Edge, Node

SPEC = DiagramSpec(
    id="d", title="T", kind="concept", question="Q?",
    nodes=(Node(id="a", label="Alpha"), Node(id="b", label="Beta", emphasis="primary")),
    edges=(Edge(source="a", target="b", label="calls"),),
)
PLACEMENTS = {
    "a": Placement("a", 0, 0, 100, 50),
    "b": Placement("b", 200, 0, 100, 50),
}


def test_emits_a_valid_excalidraw_document():
    doc = emit_excalidraw(SPEC, PLACEMENTS)
    assert doc["type"] == "excalidraw"
    assert doc["version"] == 2
    assert doc["source"] == "designcore"
    assert isinstance(doc["elements"], list)


def test_each_node_becomes_a_rectangle_at_its_placement():
    elements = emit_excalidraw(SPEC, PLACEMENTS)["elements"]
    rects = [e for e in elements if e["type"] == "rectangle"]
    assert len(rects) == 2
    first = next(r for r in rects if r["x"] == 0)
    assert (first["y"], first["width"], first["height"]) == (0, 100, 50)


def test_each_node_gets_a_bound_text_label():
    elements = emit_excalidraw(SPEC, PLACEMENTS)["elements"]
    texts = [e for e in elements if e["type"] == "text"]
    assert {t["text"] for t in texts} >= {"Alpha", "Beta"}


def test_each_edge_becomes_an_arrow_between_the_right_elements():
    elements = emit_excalidraw(SPEC, PLACEMENTS)["elements"]
    arrows = [e for e in elements if e["type"] == "arrow"]
    assert len(arrows) == 1
    assert arrows[0]["startBinding"]["elementId"] == "a"
    assert arrows[0]["endBinding"]["elementId"] == "b"


def test_primary_emphasis_gets_a_thicker_stroke():
    elements = emit_excalidraw(SPEC, PLACEMENTS)["elements"]
    b = next(e for e in elements if e.get("id") == "b")
    a = next(e for e in elements if e.get("id") == "a")
    assert b["strokeWidth"] > a["strokeWidth"]


def test_missing_placement_is_an_error_not_a_guess():
    with pytest.raises(KeyError):
        emit_excalidraw(SPEC, {"a": PLACEMENTS["a"]})
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_emit_excalidraw.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.emit.excalidraw'`

- [ ] **Step 3: Implement `emit/excalidraw.py`**

```python
"""Compile a graph spec plus placements into an .excalidraw document."""

from __future__ import annotations

from typing import Any

from designcore.layout import Placement
from designcore.spec import DiagramSpec

STROKE_WIDTH = {"normal": 1, "primary": 3, "muted": 1}
OPACITY = {"normal": 100, "primary": 100, "muted": 55}


def _base(element_id: str, x: float, y: float, width: float, height: float) -> dict[str, Any]:
    return {
        "id": element_id,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": 1,
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": [],
        "updated": 1,
        "link": None,
        "locked": False,
    }


def emit_excalidraw(spec: DiagramSpec, placements: dict[str, Placement]) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []

    for node in spec.nodes:
        box = placements[node.id]  # KeyError is correct: never invent geometry
        rect = _base(node.id, box.x, box.y, box.width, box.height)
        rect["type"] = "rectangle"
        rect["strokeWidth"] = STROKE_WIDTH[node.emphasis]
        rect["opacity"] = OPACITY[node.emphasis]
        rect["boundElements"] = [{"type": "text", "id": f"{node.id}-label"}]
        elements.append(rect)

        label = _base(f"{node.id}-label", box.x + 8, box.y + box.height / 2 - 10, box.width - 16, 20)
        label["type"] = "text"
        label["text"] = node.label
        label["originalText"] = node.label
        label["fontSize"] = 16
        label["fontFamily"] = 1
        label["textAlign"] = "center"
        label["verticalAlign"] = "middle"
        label["containerId"] = node.id
        elements.append(label)

    for index, edge in enumerate(spec.edges):
        start, end = placements[edge.source], placements[edge.target]
        x1, y1 = start.x + start.width, start.y + start.height / 2
        x2, y2 = end.x, end.y + end.height / 2
        arrow = _base(f"edge-{index}", x1, y1, x2 - x1, y2 - y1)
        arrow["type"] = "arrow"
        arrow["points"] = [[0, 0], [x2 - x1, y2 - y1]]
        arrow["strokeStyle"] = "dashed" if edge.kind in {"async", "dashed"} else "solid"
        arrow["startBinding"] = {"elementId": edge.source, "focus": 0, "gap": 4}
        arrow["endBinding"] = {"elementId": edge.target, "focus": 0, "gap": 4}
        elements.append(arrow)

        if edge.label:
            label = _base(f"edge-{index}-label", (x1 + x2) / 2 - 30, (y1 + y2) / 2 - 20, 60, 20)
            label["type"] = "text"
            label["text"] = edge.label
            label["originalText"] = edge.label
            label["fontSize"] = 12
            label["fontFamily"] = 1
            label["textAlign"] = "center"
            label["verticalAlign"] = "middle"
            label["containerId"] = None
            elements.append(label)

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "designcore",
        "elements": elements,
        "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
        "files": {},
    }
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_emit_excalidraw.py -v`
Expected: 6 passed

- [ ] **Step 5: Confirm a real Excalidraw client accepts the output**

Write a sample document to `/tmp/dc-probe/sample.excalidraw` using the emitter, then open it at excalidraw.com (File → Open). It must load without error and show two labelled boxes joined by an arrow. Record the result in the task's commit message; if it fails to load, fix the emitter before committing.

- [ ] **Step 6: Commit**

```bash
git add src/designcore/emit/excalidraw.py tests/test_emit_excalidraw.py
git commit -m "feat: add excalidraw emitter driven by graphviz placements"
```

---

### Task 10: draw.io emitter

**Files:**
- Create: `src/designcore/emit/drawio.py`
- Test: `tests/test_emit_drawio.py`

**Interfaces:**
- Consumes: `designcore.spec.DiagramSpec`, `designcore.emit.mermaid.emit_mermaid`.
- Produces: `designcore.emit.drawio.Converter` (a `Callable[[str], str]` alias: Mermaid text in, mxGraph XML out), `designcore.emit.drawio.mcp_converter(run=subprocess.run) -> Converter`, `designcore.emit.drawio.emit_drawio(spec: DiagramSpec, convert: Converter) -> str`, `designcore.emit.drawio.restyle(xml: str, spec: DiagramSpec) -> str`.

The conversion is delegated to the official `@drawio/mcp` (ELK layout + libavoid routing upstream); DesignCore only applies role/emphasis styling afterwards. `convert` is injected so tests need neither Node nor network. Build `mcp_converter` to match whatever invocation Task 2 Step 3 recorded.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_emit_drawio.py`:

```python
from xml.etree import ElementTree

from designcore.emit.drawio import emit_drawio, restyle
from designcore.spec import DiagramSpec, Edge, Node

SPEC = DiagramSpec(
    id="d", title="T", kind="container", question="Q?",
    nodes=(Node(id="a", label="Alpha"), Node(id="b", label="Beta", emphasis="primary")),
    edges=(Edge(source="a", target="b"),),
)

CONVERTED = """<mxfile><diagram name="d"><mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="a" value="Alpha" style="rounded=0;" vertex="1" parent="1"><mxGeometry x="0" y="0" width="120" height="60" as="geometry"/></mxCell>
<mxCell id="b" value="Beta" style="rounded=0;" vertex="1" parent="1"><mxGeometry x="200" y="0" width="120" height="60" as="geometry"/></mxCell>
</root></mxGraphModel></diagram></mxfile>"""


def test_passes_mermaid_to_the_converter():
    seen = {}

    def convert(mermaid: str) -> str:
        seen["input"] = mermaid
        return CONVERTED

    emit_drawio(SPEC, convert)
    assert seen["input"].startswith("flowchart")
    assert "Alpha" in seen["input"]


def test_returns_parseable_mxfile_xml():
    xml = emit_drawio(SPEC, lambda _: CONVERTED)
    assert ElementTree.fromstring(xml).tag == "mxfile"


def test_restyle_applies_emphasis_to_the_matching_cell():
    xml = restyle(CONVERTED, SPEC)
    root = ElementTree.fromstring(xml)
    styles = {c.get("id"): c.get("style", "") for c in root.iter("mxCell")}
    assert "strokeWidth=3" in styles["b"]
    assert "strokeWidth=3" not in styles["a"]


def test_restyle_preserves_geometry_untouched():
    xml = restyle(CONVERTED, SPEC)
    root = ElementTree.fromstring(xml)
    geometry = next(
        c.find("mxGeometry") for c in root.iter("mxCell") if c.get("id") == "b"
    )
    assert geometry.get("x") == "200"
    assert geometry.get("width") == "120"


def test_restyle_ignores_cells_with_no_matching_node():
    xml = restyle(CONVERTED, DiagramSpec(id="d", title="T", kind="container", question="Q?"))
    assert ElementTree.fromstring(xml).tag == "mxfile"
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_emit_drawio.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.emit.drawio'`

- [ ] **Step 3: Implement `emit/drawio.py`**

```python
"""Compile a graph spec to editable mxGraph XML via the official draw.io MCP.

Layout and edge routing belong to upstream (ELK + libavoid). DesignCore only
adds role and emphasis styling on top of the geometry it receives.
"""

from __future__ import annotations

import subprocess
from typing import Callable
from xml.etree import ElementTree

from designcore.emit.mermaid import emit_mermaid
from designcore.render import BackendMissing, RenderError
from designcore.spec import DiagramSpec

Converter = Callable[[str], str]

EMPHASIS_STYLE = {"normal": "", "primary": "strokeWidth=3;", "muted": "opacity=55;"}
ROLE_STYLE = {
    "actor": "shape=umlActor;",
    "service": "rounded=1;",
    "store": "shape=cylinder3;",
    "infra": "rounded=0;",
    "external": "rounded=0;dashed=1;",
    "note": "shape=note;",
}


def mcp_converter(run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> Converter:
    """Return a converter backed by @drawio/mcp's Mermaid to XML tool.

    Match the invocation recorded in docs/plans/2026-08-16-render-backend-findings.md.
    """

    def convert(mermaid: str) -> str:
        result = run(
            ["npx", "-y", "@drawio/mcp", "convert", "--from", "mermaid", "--to", "xml"],
            input=mermaid,
            capture_output=True,
            text=True,
        )
        if result.returncode == 127:
            raise BackendMissing(
                "node/npx is not available, so draw.io conversion cannot run. "
                "Install Node.js 20+ (nvm install --lts)"
            )
        if result.returncode != 0:
            raise RenderError(f"@drawio/mcp conversion failed: {result.stderr.strip()}")
        return result.stdout

    return convert


def restyle(xml: str, spec: DiagramSpec) -> str:
    """Apply role and emphasis styling to converted cells, leaving geometry alone."""
    by_id = {node.id: node for node in spec.nodes}
    root = ElementTree.fromstring(xml)
    for cell in root.iter("mxCell"):
        node = by_id.get(cell.get("id", ""))
        if node is None:
            continue
        style = cell.get("style", "")
        if style and not style.endswith(";"):
            style += ";"
        cell.set("style", style + ROLE_STYLE[node.role] + EMPHASIS_STYLE[node.emphasis])
    return ElementTree.tostring(root, encoding="unicode")


def emit_drawio(spec: DiagramSpec, convert: Converter) -> str:
    """Compile the spec to styled mxGraph XML."""
    return restyle(convert(emit_mermaid(spec)), spec)
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_emit_drawio.py -v`
Expected: all golden-XML tests pass (this task's body is superseded by amendment A1; test count follows the amended tests)

- [ ] **Step 5: Verify the real converter**

```bash
uv run python -c "
from designcore.emit.drawio import emit_drawio, mcp_converter
from designcore.spec import DiagramSpec, Node, Edge
s = DiagramSpec(id='d', title='T', kind='container', question='Q?',
                nodes=(Node(id='a', label='Alpha'), Node(id='b', label='Beta')),
                edges=(Edge(source='a', target='b'),))
open('/tmp/dc-probe/real.drawio','w').write(emit_drawio(s, mcp_converter()))
print('written')
"
```

Expected: a `.drawio` file that opens in draw.io with two connected, non-overlapping boxes. If the `mcp_converter` command line does not match reality, correct it here against the Task 2 findings and re-run.

- [ ] **Step 6: Commit**

```bash
git add src/designcore/emit/drawio.py tests/test_emit_drawio.py
git commit -m "feat: add owned drawio emitter driven by graphviz placements"
```

---

### Task 11: draw.io and Excalidraw renderers

**Files:**
- Create: `src/designcore/render/drawio.py`
- Create: `src/designcore/render/excalidraw.py`
- Test: `tests/test_render_backends.py`

**Interfaces:**
- Consumes: `designcore.render.BackendMissing`, `designcore.render.RenderError`.
- Produces: `designcore.render.drawio.render_drawio(source, out_dir, run=subprocess.run, which=shutil.which) -> list[Path]`, `designcore.render.excalidraw.render_excalidraw(source, out_dir, run=subprocess.run, which=shutil.which) -> list[Path]`. Both return `[svg_path, png_path]` and share the Task 6 signature.

Use the exact invocations recorded in `docs/plans/2026-08-16-render-backend-findings.md`. If that document says draw.io export needs `xvfb-run -a`, the command below must include it. If it says no Excalidraw renderer works, implement `render_excalidraw` to raise `BackendMissing` with that explanation and skip its render tests — do not fake a rendered file.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render_backends.py`:

```python
import subprocess
from pathlib import Path

import pytest

from designcore.render import BackendMissing, RenderError
from designcore.render.drawio import render_drawio


def _ok(cmd, **kwargs):
    Path(cmd[cmd.index("-o") + 1]).write_text("rendered", encoding="utf-8")
    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def test_drawio_missing_backend_names_the_install_command(tmp_path):
    src = tmp_path / "d.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")
    with pytest.raises(BackendMissing, match="snap install drawio"):
        render_drawio(src, tmp_path / "out", run=_ok, which=lambda c: None)


def test_drawio_renders_svg_and_png(tmp_path):
    src = tmp_path / "d.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")
    outputs = render_drawio(src, tmp_path / "out", run=_ok, which=lambda c: "/snap/bin/drawio")
    assert [p.suffix for p in outputs] == [".svg", ".png"]
    assert all(p.exists() for p in outputs)


def test_drawio_nonzero_exit_raises_render_error(tmp_path):
    src = tmp_path / "d.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")

    def fail(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="cannot open display")

    with pytest.raises(RenderError, match="cannot open display"):
        render_drawio(src, tmp_path / "out", run=fail, which=lambda c: "/snap/bin/drawio")
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_render_backends.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.render.drawio'`

- [ ] **Step 3: Implement `render/drawio.py`**

Adjust `_command` to match the Task 2 findings — add the `xvfb-run -a` prefix and/or `--no-sandbox` only if the probe showed they are required.

```python
"""Export .drawio files with the draw.io CLI."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

from designcore.render import BackendMissing, RenderError

INSTALL_HINT = "sudo snap install drawio"


def _command(source: Path, target: Path, fmt: str) -> list[str]:
    return ["drawio", "-x", "-f", fmt, "-o", str(target), str(source)]


def render_drawio(
    source: Path,
    out_dir: Path,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> list[Path]:
    if which("drawio") is None:
        raise BackendMissing(
            f"the draw.io CLI is not installed, so this diagram cannot be verified. "
            f"Install it with: {INSTALL_HINT}"
        )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    for fmt, suffix in (("svg", ".svg"), ("png", ".png")):
        target = out_dir / (Path(source).stem + suffix)
        result = run(_command(Path(source), target, fmt), capture_output=True, text=True)
        if result.returncode != 0:
            raise RenderError(f"drawio export failed for {source}: {result.stderr.strip()}")
        outputs.append(target)
    return outputs
```

- [ ] **Step 4: Implement `render/excalidraw.py` per the Task 2 findings**

If the `@excalidraw/utils` probe succeeded, write a Node helper script alongside this module and shell out to it, mirroring `render_drawio`'s structure and returning `[svg, png]`. If the probe failed, implement exactly this, and nothing more:

```python
"""Rendering .excalidraw documents.

The Task 2 probe found no working renderer; see
docs/plans/2026-08-16-render-backend-findings.md. Until one exists,
Excalidraw diagrams are verified by lint only, and this module says so
rather than allowing an unverified diagram to be reported as complete.
"""

from __future__ import annotations

from pathlib import Path

from designcore.render import BackendMissing


def render_excalidraw(source: Path, out_dir: Path, **_kwargs) -> list[Path]:
    raise BackendMissing(
        "no working .excalidraw renderer is available, so this diagram cannot be "
        "visually verified; it has passed structural lint only"
    )
```

- [ ] **Step 5: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_render_backends.py -v`
Expected: 5 passed (amendment A3 added two tests)

- [ ] **Step 6: Verify draw.io export against the real binary**

```bash
uv run python -c "
from pathlib import Path
from designcore.render.drawio import render_drawio
print(render_drawio(Path('/tmp/dc-probe/real.drawio'), Path('/tmp/dc-probe/out')))
"
```

Expected: two non-empty files. A failure here means `_command` does not match the Task 2 findings — fix it before committing.

- [ ] **Step 7: Commit**

```bash
git add src/designcore/render/drawio.py src/designcore/render/excalidraw.py tests/test_render_backends.py
git commit -m "feat: add drawio and excalidraw render backends"
```

---

### Task 12: Diagram manifest

**Files:**
- Create: `src/designcore/manifest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `designcore.lint.Finding`.
- Produces: `designcore.manifest.DiagramEntry(id, title, kind, format, question, spec, source, rendered, embedded_in, hand_owned, generated_by, generated_at)`, `designcore.manifest.Manifest(version, diagrams)`, `load_manifest(path) -> Manifest`, `save_manifest(manifest, path) -> None`, `upsert(manifest, entry) -> Manifest`, `check_manifest(root: Path) -> list[Finding]`.

The manifest is what lets a later agent regenerate a diagram without re-deriving why it exists — `question` and `kind` are the load-bearing fields. `hand_owned` implements the design's ownership rule: `render` must refuse to overwrite a hand-edited compiled source.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_manifest.py`:

```python
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
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.manifest'`

- [ ] **Step 3: Implement `manifest.py`**

```python
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
    diagrams = list(manifest.diagrams)
    for index, existing in enumerate(diagrams):
        if existing.id == entry.id:
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
        source = root / entry.source
        if not source.exists():
            findings.append(
                Finding("MISSING_SOURCE", "error", f"source {entry.source} is missing", entry.id)
            )
            continue

        for rendered in entry.rendered:
            target = root / rendered
            if not target.exists():
                findings.append(
                    Finding("MISSING_RENDER", "error", f"render {rendered} is missing", entry.id)
                )
            elif target.stat().st_mtime < source.stat().st_mtime:
                findings.append(
                    Finding(
                        "STALE_RENDER",
                        "warning",
                        f"{rendered} is older than its source; re-run designcore render",
                        entry.id,
                    )
                )

        for embed in entry.embedded_in:
            if not (root / embed).exists():
                findings.append(
                    Finding("BROKEN_EMBED", "warning", f"embed target {embed} is missing", entry.id)
                )

    return findings
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/designcore/manifest.py tests/test_manifest.py
git commit -m "feat: add diagrams.yaml manifest with integrity checks"
```

---

### Task 13: Pipeline and full CLI

**Files:**
- Create: `src/designcore/pipeline.py`
- Modify: `src/designcore/cli.py` (replace the Task 1 `main` with the full subcommand set)
- Test: `tests/test_pipeline.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 3–12.
- Produces: `designcore.pipeline.compile_diagram(spec, fmt, out_root, deps) -> DiagramEntry`, `designcore.pipeline.Deps(render_map, layout, layout_groups)` (a container for injected backends; amendment A4 removed `convert`), `designcore.pipeline.lint_diagram(spec, placements, svg_path) -> list[Finding]`, and the CLI subcommands `new`, `render`, `lint`, `check`, `doctor`.

`Deps` exists so the pipeline is testable without any external binary. Production callers use `Deps.default()`.

- [ ] **Step 1: Write the failing pipeline tests**

Create `tests/test_pipeline.py`:

```python
from pathlib import Path

import pytest

from designcore.layout import Placement
from designcore.pipeline import Deps, compile_diagram, lint_diagram
from designcore.render import BackendMissing
from designcore.spec import DiagramSpec, Edge, Node

SPEC = DiagramSpec(
    id="request-flow", title="Request flow", kind="flow", question="What happens on request?",
    direction="LR",
    nodes=(Node(id="a", label="A"), Node(id="b", label="B")),
    edges=(Edge(source="a", target="b"),),
)


def _deps(tmp_path: Path) -> Deps:
    def fake_render(source: Path, out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        svg = out_dir / (source.stem + ".svg")
        png = out_dir / (source.stem + ".png")
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"/>', encoding="utf-8")
        png.write_bytes(b"png")
        return [svg, png]

    return Deps(
        convert=lambda mermaid: "<mxfile><diagram><mxGraphModel><root/></mxGraphModel></diagram></mxfile>",
        render_map={"mermaid": fake_render, "drawio": fake_render, "excalidraw": fake_render},
        layout=lambda spec: {
            "a": Placement("a", 0, 0, 100, 50),
            "b": Placement("b", 200, 0, 100, 50),
        },
    )


def test_compile_writes_source_and_renders_for_mermaid(tmp_path):
    entry = compile_diagram(SPEC, "mermaid", tmp_path, _deps(tmp_path))
    assert (tmp_path / entry.source).exists()
    assert (tmp_path / entry.source).suffix == ".mmd"
    assert all((tmp_path / r).exists() for r in entry.rendered)
    assert entry.question == SPEC.question


def test_compile_writes_drawio_xml(tmp_path):
    entry = compile_diagram(SPEC, "drawio", tmp_path, _deps(tmp_path))
    assert (tmp_path / entry.source).suffix == ".drawio"
    assert (tmp_path / entry.source).read_text(encoding="utf-8").startswith("<mxfile")


def test_compile_writes_excalidraw_json(tmp_path):
    import json

    entry = compile_diagram(SPEC, "excalidraw", tmp_path, _deps(tmp_path))
    doc = json.loads((tmp_path / entry.source).read_text(encoding="utf-8"))
    assert doc["type"] == "excalidraw"


def test_compile_refuses_to_overwrite_a_hand_owned_source(tmp_path):
    deps = _deps(tmp_path)
    compile_diagram(SPEC, "mermaid", tmp_path, deps)
    with pytest.raises(PermissionError, match="hand_owned"):
        compile_diagram(SPEC, "mermaid", tmp_path, deps, hand_owned=True)


def test_compile_propagates_backend_missing(tmp_path):
    def missing(source, out_dir):
        raise BackendMissing("mmdc is not installed")

    deps = Deps(convert=lambda m: "", render_map={"mermaid": missing}, layout=lambda s: {})
    with pytest.raises(BackendMissing):
        compile_diagram(SPEC, "mermaid", tmp_path, deps)


def test_lint_diagram_combines_all_three_check_families(tmp_path):
    svg = tmp_path / "d.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"/>', encoding="utf-8")
    placements = {"a": Placement("a", 0, 0, 100, 50), "b": Placement("b", 50, 0, 100, 50)}
    codes = {f.code for f in lint_diagram(SPEC, placements, svg)}
    assert "NODE_OVERLAP" in codes
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'designcore.pipeline'`

- [ ] **Step 3: Implement `pipeline.py`**

```python
"""spec in, verified diagram out."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from designcore.emit.drawio import emit_drawio, mcp_converter
from designcore.emit.excalidraw import emit_excalidraw
from designcore.emit.mermaid import emit_mermaid
from designcore.layout import Placement, layout_spec
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


@dataclass(frozen=True)
class Deps:
    convert: Callable[[str], str]
    render_map: dict[str, Callable[[Path, Path], list[Path]]]
    layout: Callable[[DiagramSpec], dict[str, Placement]]

    @classmethod
    def default(cls) -> "Deps":
        return cls(
            convert=mcp_converter(),
            render_map={
                "mermaid": render_mermaid,
                "drawio": render_drawio,
                "excalidraw": render_excalidraw,
            },
            layout=layout_spec,
        )


def _source_text(spec: DiagramSpec, fmt: str, deps: Deps) -> str:
    if fmt == "mermaid":
        return emit_mermaid(spec)
    if fmt == "drawio":
        return emit_drawio(spec, deps.convert)
    if fmt == "excalidraw":
        return json.dumps(emit_excalidraw(spec, deps.layout(spec)), indent=2)
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

    rendered = deps.render_map[fmt](source_path, out_root / "out")

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
    spec: DiagramSpec, placements: dict[str, Placement], svg_path: Path | None
) -> list[Finding]:
    findings = check_structure(spec) + check_density(spec)
    findings += check_geometry(list(placements.values()))
    if svg_path is not None and Path(svg_path).exists():
        findings += check_svg_bounds(Path(svg_path))
    return findings
```

- [ ] **Step 4: Run the pipeline tests and make sure they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: 6 passed

- [ ] **Step 5: Write the failing CLI tests**

Create `tests/test_cli.py`:

```python
from pathlib import Path

import yaml

from designcore.cli import main


def test_new_scaffolds_a_spec_with_the_question_prompt(tmp_path, capsys):
    code = main(["new", "request-flow", "--kind", "flow", "--root", str(tmp_path), "--format", "mermaid"])
    assert code == 0
    spec_file = tmp_path / "src" / "request-flow.spec.yaml"
    data = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
    assert data["kind"] == "flow"
    assert "question" in data
    assert data["nodes"] == []


def test_check_reports_findings_and_exit_code(tmp_path):
    (tmp_path / "diagrams.yaml").write_text(
        yaml.safe_dump({
            "version": 1,
            "diagrams": [{
                "id": "d", "title": "T", "kind": "flow", "format": "mermaid",
                "question": "Q?", "spec": "src/d.spec.yaml", "source": "src/d.mmd",
                "rendered": [], "embedded_in": [],
            }],
        }),
        encoding="utf-8",
    )
    assert main(["check", "--root", str(tmp_path)]) == 1


def test_lint_on_a_clean_spec_exits_zero(tmp_path):
    spec = tmp_path / "src" / "d.spec.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        yaml.safe_dump({
            "id": "d", "title": "T", "kind": "flow", "question": "Q?",
            "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "edges": [{"from": "a", "to": "b"}],
        }),
        encoding="utf-8",
    )
    assert main(["lint", "d", "--root", str(tmp_path)]) == 0


def test_unknown_command_is_rejected(capsys):
    try:
        main(["frobnicate"])
    except SystemExit as exc:
        assert exc.code != 0
```

- [ ] **Step 6: Run them to make sure they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `main` does not accept `new`, `lint`, or `check` yet.

- [ ] **Step 7: Replace `cli.py` with the full subcommand set**

```python
"""designcore command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from designcore.doctor import check_backends
from designcore.lint import has_errors
from designcore.manifest import Manifest, check_manifest, load_manifest, save_manifest, upsert
from designcore.pipeline import Deps, compile_diagram, lint_diagram
from designcore.spec import load_spec

DEFAULT_FORMAT = {
    "context": "drawio", "container": "drawio", "deployment": "drawio", "network": "drawio",
    "sequence": "mermaid", "state": "mermaid", "flow": "mermaid", "concept": "excalidraw",
}


def _print_findings(findings) -> None:
    for finding in findings:
        marker = "ERROR " if finding.severity == "error" else "warn  "
        subject = f" [{finding.subject}]" if finding.subject else ""
        print(f"  {marker} {finding.code}{subject}: {finding.message}")


def _cmd_new(args: argparse.Namespace) -> int:
    root = Path(args.root)
    target = root / "src" / f"{args.id}.spec.yaml"
    if target.exists():
        print(f"{target} already exists")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    scaffold = {
        "id": args.id,
        "title": args.id.replace("-", " ").capitalize(),
        "kind": args.kind,
        "question": "REPLACE ME: the one question this diagram answers",
        "direction": "TB",
        "nodes": [],
        "edges": [],
        "groups": [],
    }
    target.write_text(yaml.safe_dump(scaffold, sort_keys=False), encoding="utf-8")
    fmt = args.format or DEFAULT_FORMAT[args.kind]
    print(f"created {target} (format: {fmt})")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    root = Path(args.root)
    spec = load_spec(root / "src" / f"{args.id}.spec.yaml")
    fmt = args.format or DEFAULT_FORMAT[spec.kind]
    manifest_path = root / "diagrams.yaml"
    manifest = load_manifest(manifest_path) if manifest_path.exists() else Manifest(1, [])
    existing = next((d for d in manifest.diagrams if d.id == spec.id), None)

    entry = compile_diagram(
        spec, fmt, root, Deps.default(), hand_owned=bool(existing and existing.hand_owned)
    )
    save_manifest(upsert(manifest, entry), manifest_path)
    print(f"rendered {entry.id}: {', '.join(entry.rendered)}")
    return 0


def _cmd_lint(args: argparse.Namespace) -> int:
    root = Path(args.root)
    spec = load_spec(root / "src" / f"{args.id}.spec.yaml")
    placements = Deps.default().layout(spec) if spec.nodes else {}
    svg = root / "out" / f"{args.id}.svg"
    findings = lint_diagram(spec, placements, svg if svg.exists() else None)
    if not findings:
        print(f"{args.id}: clean")
        return 0
    _print_findings(findings)
    return 1 if has_errors(findings) else 0


def _cmd_check(args: argparse.Namespace) -> int:
    findings = check_manifest(Path(args.root))
    if not findings:
        print("manifest: clean")
        return 0
    _print_findings(findings)
    return 1


def _cmd_doctor(_args: argparse.Namespace) -> int:
    missing = 0
    for status in check_backends():
        if status.available:
            print(f"  ok       {status.backend.name:<10} {status.path}")
        else:
            missing += 1
            print(f"  MISSING  {status.backend.name:<10} {status.backend.purpose}")
            print(f"           install: {status.backend.install_hint}")
    if missing:
        print(f"\n{missing} backend(s) missing. Diagrams cannot be verified without them.")
    return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="designcore")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_root(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--root", default="docs/diagrams", help="diagram root directory")

    new = subparsers.add_parser("new", help="Scaffold a diagram spec")
    new.add_argument("id")
    new.add_argument("--kind", required=True, choices=sorted(DEFAULT_FORMAT))
    new.add_argument("--format", choices=["mermaid", "drawio", "excalidraw"])
    add_root(new)
    new.set_defaults(func=_cmd_new)

    render = subparsers.add_parser("render", help="Compile and render a diagram")
    render.add_argument("id")
    render.add_argument("--format", choices=["mermaid", "drawio", "excalidraw"])
    add_root(render)
    render.set_defaults(func=_cmd_render)

    lint = subparsers.add_parser("lint", help="Check a diagram spec and its render")
    lint.add_argument("id")
    add_root(lint)
    lint.set_defaults(func=_cmd_lint)

    check = subparsers.add_parser("check", help="Validate manifest integrity")
    add_root(check)
    check.set_defaults(func=_cmd_check)

    doctor = subparsers.add_parser("doctor", help="Report render backend availability")
    doctor.set_defaults(func=_cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: Run the whole suite**

Run: `uv run pytest -v`
Expected: all tests pass, including the Task 1 doctor tests.

- [ ] **Step 9: Commit**

```bash
git add src/designcore/pipeline.py src/designcore/cli.py tests/test_pipeline.py tests/test_cli.py
git commit -m "feat: wire spec-to-verified-diagram pipeline behind the CLI"
```

---

### Task 14: End-to-end verification on a real diagram

**Files:**
- Create: `tests/test_end_to_end.py`
- Create: `examples/docs/diagrams/src/designcore-pipeline.spec.yaml`

**Interfaces:**
- Consumes: the full CLI.
- Produces: `examples/docs/diagrams/` — a worked example that doubles as the skills' reference output.

This task proves the whole chain on real binaries, and produces the example a skill can point at.

- [ ] **Step 1: Write the example spec**

Create `examples/docs/diagrams/src/designcore-pipeline.spec.yaml`:

```yaml
id: designcore-pipeline
title: DesignCore compile pipeline
kind: flow
question: "How does a graph spec become a verified diagram?"
direction: LR
nodes:
  - id: spec
    label: .spec.yaml
    role: store
  - id: emit
    label: Emitter
    role: service
  - id: layout
    label: Graphviz
    role: infra
  - id: render
    label: Renderer
    role: service
  - id: lint
    label: Lint
    role: service
    emphasis: primary
  - id: manifest
    label: diagrams.yaml
    role: store
edges:
  - from: spec
    to: emit
  - from: layout
    to: emit
    label: geometry
  - from: emit
    to: render
    label: source file
  - from: render
    to: lint
    label: svg + png
  - from: lint
    to: manifest
    label: entry
```

- [ ] **Step 2: Write the end-to-end test**

Create `tests/test_end_to_end.py`:

```python
import shutil
from pathlib import Path

import pytest

from designcore.cli import main

EXAMPLE = Path("examples/docs/diagrams/src/designcore-pipeline.spec.yaml")
needs_backends = pytest.mark.skipif(
    shutil.which("mmdc") is None or shutil.which("dot") is None,
    reason="requires mmdc and dot; run designcore doctor",
)


@needs_backends
def test_renders_and_lints_the_example_diagram(tmp_path):
    (tmp_path / "src").mkdir(parents=True)
    shutil.copy(EXAMPLE, tmp_path / "src" / EXAMPLE.name)

    assert main(["render", "designcore-pipeline", "--root", str(tmp_path), "--format", "mermaid"]) == 0
    assert (tmp_path / "out" / "designcore-pipeline.svg").stat().st_size > 0
    assert main(["lint", "designcore-pipeline", "--root", str(tmp_path)]) == 0
    assert main(["check", "--root", str(tmp_path)]) == 0
```

- [ ] **Step 3: Run it**

Run: `uv run pytest tests/test_end_to_end.py -v`
Expected: PASS. If it skips, install the backends per `designcore doctor` and re-run — this task is not complete on a skip.

- [ ] **Step 4: Generate the committed example in all three formats**

```bash
uv run designcore render designcore-pipeline --root examples/docs/diagrams --format mermaid
uv run designcore render designcore-pipeline --root examples/docs/diagrams --format drawio
uv run designcore render designcore-pipeline --root examples/docs/diagrams --format excalidraw
uv run designcore check --root examples/docs/diagrams
```

Expected: sources in `src/`, renders in `out/`, a populated `diagrams.yaml`, and a clean `check`. If the Excalidraw renderer was found unavailable in Task 2, that command will raise `BackendMissing` — that is the designed behavior; note it and continue.

- [ ] **Step 5: Look at the rendered PNGs**

Open `examples/docs/diagrams/out/*.png` and confirm each is readable: no overlapping boxes, no truncated labels, arrows connecting the right nodes. This is the human equivalent of the vision pass the skills perform. If a diagram is unreadable, fix the emitter and re-run — do not commit an unreadable example.

- [ ] **Step 6: Commit**

```bash
git add examples tests/test_end_to_end.py
git commit -m "test: verify the full pipeline end to end on a real diagram"
```

---

### Task 15: Shared skill references

**Files:**
- Create: `skills/_shared/references/format-selection.md`
- Create: `skills/_shared/references/legibility.md`
- Create: `skills/_shared/references/pipeline.md`
- Create: `skills/_shared/references/mermaid.md`
- Create: `skills/_shared/references/drawio.md`
- Create: `skills/_shared/references/excalidraw.md`

**Interfaces:**
- Consumes: the CLI surface from Task 13.
- Produces: reference files the three skill bundles link to. Format mechanics live here exactly once.

- [ ] **Step 1: Write `format-selection.md`**

Content, stated as a decision rubric, not prose:

- **Mermaid** — default. Choose it for anything embedded in repo docs, reviewed in PRs, or under ~15 nodes. Renders natively on GitHub, Obsidian, and Claude artifacts; diffs cleanly; costs least.
- **draw.io** — detailed system architecture, branded cloud/network icons, multi-page drill-down, or anything a human will later open and hand-edit.
- **Excalidraw** — concept sketches and teaching diagrams where deliberate informality signals "this is a mental model, not a spec".
- Include the `kind → format` default table from `cli.DEFAULT_FORMAT` verbatim, and state that `--format` overrides it.

- [ ] **Step 2: Write `legibility.md`**

The rules the vision pass judges against:

- One diagram answers one question. A `question:` needing the word "and" means split it.
- Entry point obvious: the reader's eye should find where to start within two seconds.
- Consistent altitude: never mix "what talks to what" with "how it is deployed".
- Label every edge that is not obvious; leave obvious ones bare rather than adding noise.
- Emphasis is scarce — at most two `primary` nodes per diagram, or emphasis means nothing.
- Grouping carries meaning (trust boundary, deployment unit, ownership); decorative groups are noise.

- [ ] **Step 3: Write `pipeline.md`**

The exact loop every skill follows, with commands:

```
1. Write docs/diagrams/src/<id>.spec.yaml     (designcore new <id> --kind <k>)
2. designcore render <id>                      → source + svg + png + manifest entry
3. designcore lint <id>                        → fix every ERROR; judge each warning
4. Read the rendered PNG                       → judge against legibility.md
5. Fix the spec and repeat from 2              → maximum 2 vision rounds
6. designcore check                            → manifest integrity
7. Embed the SVG in the doc; record embedded_in
```

State the two hard rules explicitly: **never hand-write coordinates into any file**, and **never report a diagram complete without a successful render** — on `BackendMissing`, report the missing backend and its install command instead.

- [ ] **Step 4: Write the three format reference files**

Each covers only mechanics: `mermaid.md` — supported node/edge syntax the emitter produces and how to embed in markdown; `drawio.md` — that layout and routing come from `@drawio/mcp` upstream, how to request branded icons via its `search_shapes`, and that hand-edits require `hand_owned: true` in the manifest; `excalidraw.md` — that positions come from Graphviz, and the current render/verification status recorded in `docs/plans/2026-08-16-render-backend-findings.md`.

- [ ] **Step 5: Commit**

```bash
git add skills/_shared
git commit -m "docs: add shared diagramming references for the skill bundles"
```

---

### Task 16: The three skill bundles

**Files:**
- Create: `skills/architecture-diagram/{SKILL.md,manifest.json}`
- Create: `skills/flow-diagram/{SKILL.md,manifest.json}`
- Create: `skills/concept-sketch/{SKILL.md,manifest.json}`
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: `skills/_shared/references/*`.
- Produces: three GearCore-compatible skill bundles.

- [ ] **Step 1: Write the failing test**

Create `tests/test_skills.py`:

```python
import json
from pathlib import Path

import pytest
import yaml

BUNDLES = ["architecture-diagram", "flow-diagram", "concept-sketch"]


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no YAML frontmatter"
    return yaml.safe_load(text.split("---\n")[1])


@pytest.mark.parametrize("bundle", BUNDLES)
def test_bundle_has_skill_and_manifest(bundle):
    root = Path("skills") / bundle
    assert (root / "SKILL.md").exists()
    assert (root / "manifest.json").exists()


@pytest.mark.parametrize("bundle", BUNDLES)
def test_frontmatter_name_matches_directory(bundle):
    data = _frontmatter(Path("skills") / bundle / "SKILL.md")
    assert data["name"] == bundle
    assert data["description"].strip()


@pytest.mark.parametrize("bundle", BUNDLES)
def test_manifest_is_valid_json_naming_the_bundle(bundle):
    data = json.loads((Path("skills") / bundle / "manifest.json").read_text(encoding="utf-8"))
    assert data["name"] == bundle
    assert data["category"] == "design"
    assert data["activation"]["triggers"]


@pytest.mark.parametrize("bundle", BUNDLES)
def test_skill_states_the_two_hard_rules(bundle):
    text = (Path("skills") / bundle / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "never" in text and "coordinate" in text
    assert "render" in text


@pytest.mark.parametrize("bundle", BUNDLES)
def test_skill_links_shared_references(bundle):
    text = (Path("skills") / bundle / "SKILL.md").read_text(encoding="utf-8")
    assert "_shared/references/pipeline.md" in text
    assert "_shared/references/legibility.md" in text
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_skills.py -v`
Expected: FAIL — the bundles do not exist.

- [ ] **Step 3: Write `skills/architecture-diagram/SKILL.md`**

```markdown
---
name: architecture-diagram
description: Use when documenting how a system is structured — system context, containers and services, deployment topology, or network layout. Produces a verified draw.io or Mermaid diagram with a spec, a render, and a manifest entry in the project's docs/diagrams/.
---

# Architecture Diagram

Draw what the system *is*: which parts exist, what they own, and where the boundaries fall.

## Before drawing

State the one question this diagram answers, in a sentence, in the spec's `question:` field.
If that sentence needs the word "and", you have two diagrams. Split them.

Pick the altitude and hold it:

- **context** — the system as one box, plus the external actors and systems it talks to.
- **container** — the deployable/runnable parts inside the system and how they communicate.
- **deployment** — where those parts actually run: hosts, regions, clusters.
- **network** — addresses, subnets, routes, firewalls.

Never mix altitudes. "What talks to what" and "where it runs" are different diagrams.

## Procedure

Follow [../_shared/references/pipeline.md](../_shared/references/pipeline.md) exactly.
Judge the rendered PNG against [../_shared/references/legibility.md](../_shared/references/legibility.md).
Choose the format with [../_shared/references/format-selection.md](../_shared/references/format-selection.md);
architecture defaults to draw.io, but Mermaid is right for small in-repo diagrams.
Format mechanics: [../_shared/references/drawio.md](../_shared/references/drawio.md).

## Hard rules

- **Never write coordinates.** Geometry comes from the layout engine. A spec containing `x` or `y`
  is rejected by design.
- **Never report a diagram complete without a successful render.** If a backend is missing, say
  which one and how to install it.
- Name every boundary you draw. An unlabelled box group means nothing to a reader.
```

- [ ] **Step 4: Write `skills/flow-diagram/SKILL.md`**

Same structure, with these differences in the "Before drawing" section:

```markdown
Draw what the system *does over time*: the order things happen in and where they can diverge.

- **sequence** — messages between participants, in order.
- **state** — the states a thing occupies and what moves it between them.
- **flow** — steps and branches in a process.

Discipline:
- Time flows one direction. Pick it and never reverse it mid-diagram.
- Every branch has an exit. A decision node with one outgoing edge is a bug in the diagram.
- Error paths are drawn, or the diagram states in its `question:` that it covers the happy path only.
```

Its format section defaults to Mermaid and links `../_shared/references/mermaid.md`. Keep the same
Procedure and Hard rules sections verbatim from Task 16 Step 3, with the reference links adjusted.

- [ ] **Step 5: Write `skills/concept-sketch/SKILL.md`**

Same structure, with:

```markdown
Draw a *mental model*: the idea behind the system, not its literal structure.

Discipline:
- Annotation over precision. A sketch that explains beats a schematic that documents.
- Deliberate informality signals "this is a model, not a spec" — that signal is the point.
- If a reader could mistake the sketch for the real topology, use architecture-diagram instead.
```

Its format defaults to Excalidraw and links `../_shared/references/excalidraw.md`. It must state
the current Excalidraw verification status from
`docs/plans/2026-08-16-render-backend-findings.md`: if no renderer is available, the skill says so
plainly rather than implying the sketch was visually verified.

- [ ] **Step 6: Write the three `manifest.json` files**

`skills/architecture-diagram/manifest.json`:

```json
{
  "name": "architecture-diagram",
  "version": "1.0.0",
  "description": "Verified system-structure diagrams: context, container, deployment, network.",
  "category": "design",
  "activation": {
    "strategy": "manual",
    "triggers": ["architecture", "diagram", "c4", "topology", "deployment", "system design"]
  }
}
```

`skills/flow-diagram/manifest.json` — same shape, description "Verified process diagrams: sequence, state, and flow.", triggers `["flow", "sequence", "state machine", "process", "diagram", "swimlane"]`.

`skills/concept-sketch/manifest.json` — same shape, description "Verified whiteboard-style concept sketches for explaining mental models.", triggers `["sketch", "concept", "whiteboard", "explain", "diagram", "excalidraw"]`.

- [ ] **Step 7: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_skills.py -v`
Expected: 15 passed (5 tests × 3 bundles)

- [ ] **Step 8: Commit**

```bash
git add skills tests/test_skills.py
git commit -m "feat: add architecture-diagram, flow-diagram, and concept-sketch skills"
```

---

### Task 17: GearCore registration and project docs

**Files:**
- Create: `README.md`
- Create: `ARCHITECTURE.md`
- Modify: `docs/plans/2026-08-16-designcore-design.md` (status line only)

**Interfaces:**
- Consumes: everything.
- Produces: a DesignCore that `gearcore list-skills` surfaces, and docs that point at the spec rather than restating it.

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest -v`
Expected: every test passes. Do not proceed on a failure or an unexplained skip.

- [ ] **Step 2: Register the skills with GearCore**

```bash
for skill in architecture-diagram flow-diagram concept-sketch; do
  ln -sfn "$(pwd)/skills/$skill" "$HOME/.config/gearcore/skills/$skill"
done
ln -sfn "$(pwd)/skills/_shared" "$HOME/.config/gearcore/skills/_shared"
gearcore list-skills | grep -E 'architecture-diagram|flow-diagram|concept-sketch'
```

Expected: all three listed with their descriptions. If `_shared` breaks the listing (GearCore may treat every subdirectory as a bundle), instead copy `_shared/references` into each bundle's own `references/` directory and update the SKILL.md links from `../_shared/references/` to `references/`. Re-run the Task 16 tests after any such change.

- [ ] **Step 3: Write `README.md`**

Cover: what DesignCore is in two sentences; install (`uv sync`); `designcore doctor` and the backends it needs; the five commands with one line each; a link to the example in `examples/docs/diagrams/`; and a link to the design spec for rationale. Do not restate the design.

- [ ] **Step 4: Write `ARCHITECTURE.md`**

One page: the layer diagram from the spec's §4, the module map, and the central invariant (the model never writes x/y; nothing is complete without a render). Link to `docs/plans/2026-08-16-designcore-design.md` for the decision rationale — do not duplicate the decision table, which would create a second source of truth.

- [ ] **Step 5: Update the design doc's status**

Change the `Status:` line in `docs/plans/2026-08-16-designcore-design.md` from `Approved design, not yet implemented` to `Implemented in v1 — see README.md`. If implementation diverged from the spec anywhere, fix the spec to describe what was actually built and note why.

- [ ] **Step 6: Commit**

```bash
git add README.md ARCHITECTURE.md docs/plans/
git commit -m "docs: add README and architecture overview; register skills with GearCore"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task(s) |
|---|---|
| §4 repo layout, GearCore registration | 1, 17 |
| §5 graph spec model and validation | 3 |
| §6 mermaid / drawio / excalidraw adapters | 5, 9, 10 |
| §6 format selection rubric | 15 |
| §7 render + lint + vision loop | 4, 6, 8, 11, 13, 15 |
| §8 on-disk contract, manifest, `hand_owned` | 12, 13 |
| §9 CLI surface (`new`/`render`/`lint`/`check`/`doctor`) | 1, 13 |
| §10 three purpose skills | 16 |
| §11 testing strategy | every task; golden/lint/manifest/doctor all covered |
| §13 risks R1–R4 | 2 (gate), 11 (applies findings) |
| D3 "model never writes x/y" | 3 (rejects coordinates), 7, 9 |
| D7 "no diagram done without a render" | 6, 11, 13, 15 |

No spec section is unimplemented. §12 out-of-scope items are correctly absent.

**Placeholder scan:** no TBDs. The one deliberately conditional task is Task 11 Step 4, which branches on Task 2's empirical findings; both branches are written out in full, so the executor has concrete code either way.

**Type consistency:** `Finding(code, severity, message, subject)` is identical across Tasks 4, 8, and 12. `Placement(id, x, y, width, height)` is identical in Tasks 7, 8, 9, and 13. Every renderer shares `(source, out_dir, run, which) -> list[Path]` and raises the same `BackendMissing` / `RenderError` from `designcore.render`. `DiagramEntry` field names match between Task 12 and the manifest example in the design spec's §8. `emit_mermaid` is consumed by Task 10 exactly as Task 5 defines it.

---

## Execution note

This plan is written to be executed by a different agent. Task 2 is a hard gate: its findings determine the code in Task 11 and the honesty of the `concept-sketch` skill. Do not skip it, and do not let a skipped end-to-end test in Task 14 pass for completion.
