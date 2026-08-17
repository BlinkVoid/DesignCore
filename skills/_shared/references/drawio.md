# draw.io mechanics

## DesignCore owns this emitter

Layout comes from **Graphviz**, and edge routing from the emitter's own
`edgeStyle=orthogonalEdgeStyle` declaration. Nothing is converted from Mermaid,
and no layout comes from upstream.

This corrects an earlier design: the Task 2 probe showed `@drawio/mcp` has no
headless conversion path — its `open_drawio_mermaid` tool opens an interactive
editor in a browser and returns a URL, not XML. See amendment A1 in the
implementation plan and section 2 of the render-backend findings.

`@drawio/mcp` remains optionally useful for one thing: `search_shapes`, to find
branded cloud/network icons whose style strings you can paste into a spec's
role styling. It is never in the compile path.

## What gets emitted

An `<mxfile><diagram><mxGraphModel><root>` document containing:

- the two mandatory root cells (`id="0"`, and `id="1" parent="0"`);
- one container cell per group, emitted **first** so it paints behind its
  members, with bounds from `layout_groups`;
- one vertex cell per node, with absolute geometry from `layout_spec`;
- one edge cell per edge, carrying `source`, `target`, and an orthogonal style.

Role maps to a shape (`store` becomes a cylinder, `actor` a UML actor, and so
on) and emphasis to `strokeWidth`/`opacity`.

## Labels are HTML

Every cell declares `html=1`, so draw.io parses the value as HTML. Labels are
therefore HTML-escaped before being written into the XML. This matters: a label
containing `<fast>` produced perfectly well-formed XML and a picture with the
word silently missing, because an unknown tag is dropped by the HTML parser.
The emitter handles this — do not paste raw markup into a label and expect it
to survive.

## Hand edits

A compiled `.drawio` is a build artifact and `designcore render` will overwrite
it. If someone hand-edits one and wants it kept, set `hand_owned: true` on the
manifest entry; the pipeline then refuses to overwrite it and raises
`PermissionError`. Fold the change back into the spec when you can — a
hand-owned file no longer regenerates.

## Export

Export runs through the draw.io CLI, prefixed with `xvfb-run -a` when `DISPLAY`
is unset. The snap is strictly confined and has its own private `/tmp`, so
source and output paths must live under `$HOME`; DesignCore raises a
`RenderError` explaining this rather than letting the snap report a confusing
"file not found".
