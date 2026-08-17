# Excalidraw mechanics

## Positions and routes come from Graphviz

The scene is generated: each node becomes a `rectangle` at its computed
placement with a bound `text` label, each group a labelled dashed enclosure
written ahead of its members so it paints behind them, and each edge an `arrow`
with `startBinding`/`endBinding` referencing the node ids.

Arrows **follow the Graphviz spline**, as a multi-point path with roundness type
2, so an edge bends around whatever sits between its endpoints instead of
cutting through it. Only when no route exists does the emitter fall back to
straight connection points between the two boxes — and that fallback picks its
exit axis by which one *separates* the boxes, not by the larger centre delta
(see amendments A20 and A21).

Roles map to the Excalidraw palette with hachure fill, external stays dashed and
unfilled, and emphasis maps to `strokeWidth` and `opacity`. The hand-drawn look
is Excalidraw's rendering, not randomness in the geometry: seeds are per-element
(crc32 of the node id), which varies the wobble between shapes while keeping the
scene byte-identical across runs. The layout is as deterministic as the other
formats.

Labels need no special escaping here: the document is serialized with
`json.dumps`.

## Render and verification status

Verified working. `render_excalidraw` runs a Node helper shipped at
`src/designcore/render/js/`, which installs a jsdom shim before dynamically
importing `@excalidraw/utils` (the package touches browser globals at import
time, so a static import fails). It writes SVG; headless Chrome then rasterizes
that SVG to PNG at a viewport matching the SVG's own dimensions.

Details and the probe history are in
`docs/plans/2026-08-16-render-backend-findings.md` section 3.

Two things to know:

- **The dependency is pinned to an exact prerelease**, `@excalidraw/utils`
  `0.1.3-test32`. The current stable release ships a different build that
  throws under the jsdom shim, and npm caret ranges do not match prereleases,
  so a range silently installs the broken one. See amendment A11.
- **A font warning is expected.** The shim stubs `document.fonts`/`FontFace`,
  so the export logs `Couldn't transform font-face to css for family
  "undefined"` and drops the embedded font CSS; text renders in a fallback
  font. Geometry and content are unaffected. Exit status decides success — do
  not treat that warning as a failure.

If the helper's dependencies are not installed, `render_excalidraw` raises
`BackendMissing` naming the exact `npm install --prefix ...` command. Report it
and stop; do not describe the diagram as complete.
