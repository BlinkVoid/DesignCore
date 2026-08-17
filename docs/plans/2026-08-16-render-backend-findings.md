# Render backend probe findings — R1 and R2 gate task

- **Date:** 2026-08-16
- **Task:** Task 2 (empirical gate for spec risks R1, R2; context for R3–R5)
- **Method:** run the probes, record what actually happened. No success is asserted without an exit code and an artifact.
- **Cross-reference:** risk table in `2026-08-16-designcore-design.md` §13 is updated in place from these findings.

---

## 0. Backend installation (brief Step 1)

`sudo` is unavailable on this machine (password not held), so the brief's `apt install` line
was adapted:

- **mermaid-cli** — `npm install -g @mermaid-js/mermaid-cli` → `mmdc` 11.16.0 at
  `~/.nvm/versions/node/v24.14.0/bin/mmdc` (nvm user prefix, no sudo needed).
- **graphviz** — installed via a **local-extract method, not apt**:
  1. `apt-get download graphviz libgvc6 libcgraph6 libcdt5 libpathplan4 libxdot4 libgts-0.7-5t64`
  2. `dpkg -x` each `.deb` into `~/.local/share/designcore/graphviz/rootfs`
  3. copy `rootfs/usr/sbin/libgvc6-config-update` to `~/.local/share/designcore/graphviz/bin/dot`
  4. wrapper at `~/.local/bin/dot` (on PATH) exporting `LD_LIBRARY_PATH` and `GVBINDIR` into the
     rootfs, then `exec` the extracted binary
  5. `dot -c` once to generate the plugin config inside `GVBINDIR`
  - Verified: `echo 'digraph { a -> b }' | dot -Tjson` prints JSON, exit 0.
- `doctor.py` was **not** modified; the local-extract method is recorded here only.

**Post-install doctor output (all four backends ok):**

```
  ok       mermaid    /home/user/.nvm/versions/node/v24.14.0/bin/mmdc
  ok       graphviz   /home/user/.local/bin/dot
  ok       drawio     /snap/bin/drawio
  ok       node       /home/user/.nvm/versions/node/v24.14.0/bin/node
exit=0
```

---

## 1. Probe: draw.io headless export (R1)

**Verdict: works with workaround (run from a snap-visible path — not `/tmp`).**

| Invocation | Exit | Result |
|---|---|---|
| `drawio -x -f png -o probe.png probe.drawio` from `/tmp/dc-probe` | 1 | `Error: input file/directory not found: probe.drawio` — strict snap confinement gives the snap a private `/tmp`; host `/tmp` files are invisible |
| `drawio -x -f png -o probe.png probe.drawio` from `~/dc-probe` | 0 | `probe.drawio -> probe.png`; PNG image data, 324×64, valid |
| `xvfb-run -a drawio -x -f png -o probe-xvfb.png probe.drawio` from `~/dc-probe` | 0 | identical valid PNG |

Notes:

- `--no-sandbox` was **not** required; the snap wrapper already injects it (visible in the
  process command line). The only stderr noise is a harmless dbus/AppArmor keyring warning.
- This machine has `DISPLAY=:1`, so the plain invocation worked here. `xvfb-run -a` also works
  and is the headless-safe form; `render/drawio.py` should use `xvfb-run -a` when `DISPLAY` is
  unset, and pass the input by a path under `$HOME` (or another snap-plug-visible location).

**Chosen working command:**

```bash
xvfb-run -a drawio -x -f png -o <out.png> <in.drawio>   # paths under $HOME, not /tmp
```

No fallback exporter needed. R1 is retired.

---

## 2. Probe: `@drawio/mcp` invocation surface (R4/R5 context, Task 10)

**Verdict: works as MCP stdio server only — no one-shot CLI mode; and it does NOT return mxGraph XML headlessly.**

- `npx -y @drawio/mcp --help` (exit 0): the entire surface is
  `drawio-mcp` (start stdio server), `--help`, `--version`. No conversion subcommand exists.
- Driving the server over stdio JSON-RPC (`initialize` → `tools/list`) returns tools:
  `open_drawio_xml, open_drawio_csv, open_drawio_mermaid, list_pages, get_page, set_page,
  search_shapes`.
- Calling `open_drawio_mermaid` with `{content: "graph LR; A[Alpha] --> B[Beta]"}` (the
  parameter is `content`, not `mermaid`) returns **a text message containing a
  `https://app.diagrams.net/?...#create=...` URL and "The diagram has been opened in your
  default browser"** — it opens an interactive editor session. It does not return editable
  mxGraph XML to the caller.

**Consequence for the design:** the spec's claim (§2, §6 drawio row) that `@drawio/mcp`
"accepts Mermaid as input and returns editable native mxGraph XML" is not borne out on the
stdio path. **RESOLVED 2026-08-16:** the user decided the mermaid→mxGraph conversion path is
retired in favour of an **owned Graphviz-driven mxGraph emitter** (`emit/drawio.py`, plan
Task 10) — see the "Execution amendments (2026-08-16, post-Task-2 gate)" section of
`2026-08-16-designcore-implementation-plan.md`. `search_shapes` and the multi-page tools
remain usable as documented. This is recorded in the R4/R5 rows of the risk table.

---

## 3. Probe: Excalidraw renderer (R2)

**Verdict: works with workaround (jsdom DOM shim in Node).**

| Invocation | Exit | Result |
|---|---|---|
| Brief's probe as written (`node probe.mjs`, plain Node import of `@excalidraw/utils`) | 1 | `ReferenceError: window is not defined` at module load — the package touches browser globals at import time |
| Same probe with `globalThis.window/document/navigator` set from jsdom | 1 | `ReferenceError: devicePixelRatio is not defined` |
| Full shim (below) | 0 | Valid SVG: `<svg ... viewBox="0 0 140 80" width="140" height="80">...<rect .../>...` — the test rectangle rendered with correct geometry |

**Working invocation** (`probe-jsdom.mjs`, run with `node`, after `npm install @excalidraw/utils jsdom`):

```js
import { JSDOM } from "jsdom";
const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", { url: "https://localhost/" });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
globalThis.devicePixelRatio = 1;
globalThis.location = dom.window.location;
globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
globalThis.FontFace = class FontFace {};
document.fonts = { add: () => {}, ready: Promise.resolve() };
const { exportToSvg } = await import("@excalidraw/utils"); // dynamic import AFTER shims
// exportToSvg({ elements, appState: { exportBackground: true }, files: null }) → SVGElement
```

Caveats for Task 11:

- Shims must be installed **before** importing `@excalidraw/utils` (dynamic import).
- Text elements load fonts through `document.fonts`/`FontFace`, which are stubbed here;
  text-bearing scenes need verification before the skill relies on them.
- SVG is proven; PNG would still need a rasterizer (not probed, not required for the vision
  pass if the PNG step is served by another tool).

R2 is retired: Task 11 keeps the render + vision loop, implemented through this shim. The
fallback (lint-only excalidraw) is **not** triggered.

---

## 3b. Late finding (2026-08-17, Task 6): mermaid-cli's bundled Chromium cannot start

**Verdict: works with workaround (point puppeteer at a system browser).**

Task 2 recorded `mmdc` as `ok` on the strength of `doctor`'s PATH check. That check proves the
binary exists, not that it can render. The first real invocation in Task 6 failed:

```
[FATAL:zygote_host_impl_linux.cc:129] No usable sandbox! If you are running on Ubuntu 23.10+
or another Linux distro that has disabled unprivileged user namespaces with AppArmor ...
```

`kernel.apparmor_restrict_unprivileged_userns` is `1` on this machine and sudo is unavailable
(same constraint as R3), so the sysctl cannot be relaxed.

| Invocation | Exit | Result |
|---|---|---|
| `mmdc -i real.mmd -o real.svg -b transparent` | 1 | `No usable sandbox!` — nothing written |
| `... -p '{"args":["--no-sandbox"]}'` | 0 | valid SVG, 10803 bytes — but sandbox disabled |
| `... -p '{"executablePath":"/usr/bin/google-chrome"}'` | 0 | valid SVG, 10803 bytes, **sandbox intact** |

Why the system browser works where the bundled one does not: Google Chrome ships a setuid
sandbox helper and an AppArmor profile; puppeteer's downloaded Chromium has neither, so it
cannot construct a sandbox at all under the userns restriction. `google-chrome --headless`
exits 0 on this machine, confirming it.

**Chosen behaviour (amendment A7):** `render/mermaid.py` resolves a puppeteer config at render
time — prefer `google-chrome`/`chromium`/`chromium-browser` via `executablePath` (sandbox
stays on), and only fall back to `--no-sandbox` when no system browser exists. Written to a
temporary JSON file, passed with `-p`, deleted afterwards.

**This applies to Task 11 too.** R2's PNG rasterization plan calls for headless Chrome. It
should use `/usr/bin/google-chrome` directly rather than a puppeteer-bundled Chromium, for the
same reason.

---

## 4. Summary of decisions handed to later tasks

| Risk | Outcome | Downstream instruction |
|---|---|---|
| R1 | drawio CLI export **works** | `render/drawio.py` (Task 11): `xvfb-run -a drawio -x ...` (or plain when `DISPLAY` set); input path under `$HOME`, never `/tmp` (snap confinement) |
| R6 (late) | mermaid render **works** via system Chrome | `render/mermaid.py` (Task 6, shipped): resolve a puppeteer config preferring a system browser's `executablePath`; `--no-sandbox` only as fallback. See §3b / amendment A7 |
| R2 | excalidraw SVG render **works** via jsdom shim | Task 11: keep render+vision; ship the shim in `render/excalidraw.py`'s node helper; verify text elements separately. PNG rasterization is owned by Task 11 via headless Chrome (`/usr/bin/google-chrome` is installed on this machine) |
| R3 | both tools now present | graphviz installed by local-extract (no sudo), not apt; doctor's apt-based hint is aspirational on this machine — installation is done and recorded here |
| R4/R5 | `@drawio/mcp` is stdio-only and opens a browser editor; no XML returned | **RESOLVED:** conversion path retired; Task 10 builds `emit/drawio.py` as an owned Graphviz-driven mxGraph emitter (see the plan's "Execution amendments" section). `search_shapes` / multi-page tools remain usable |

**Verification-path caveat:** the plan's Task 10 Step 5 and Task 11 Step 6 verification
commands reference `/tmp/dc-probe` paths, which **cannot** work with the strictly-confined
drawio snap (private `/tmp`, per §1). Those verifications must run from a path under `$HOME`
(e.g. `~/dc-probe`) — recorded as amendment A5 in the plan.
