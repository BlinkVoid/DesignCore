# The compile loop

Every diagramming skill follows this loop. Do not improvise around it.

```
1. Write docs/diagrams/src/<id>.spec.yaml     (designcore new <id> --kind <k>)
2. designcore render <id>                      -> source + svg + png + manifest entry
3. designcore lint <id>                        -> fix every ERROR; judge each warning
4. Read the rendered PNG                       -> judge against legibility.md
5. Fix the spec and repeat from 2              -> maximum 2 vision rounds
6. designcore check                            -> manifest integrity
7. Embed the SVG in the doc; record embedded_in
```

Outputs land in `docs/diagrams/out/<format>/<id>.svg` and `.png`.

## Two hard rules

**Never hand-write coordinates into any file.** No `x`, `y`, `width`, `height`,
or `position` in a spec — `spec.py` rejects them at parse time. Geometry comes
from Graphviz, always. If a diagram is laid out badly, change the graph or the
`direction`, never the numbers.

**Never report a diagram complete without a successful render.** A diagram that
has not rendered has not been verified. On `BackendMissing`, report the missing
backend and the exact install command it names, and stop — do not describe the
diagram as done, and do not fall back to lint-only.

## Reading step 4 properly

Step 4 is not a formality. Lint proves geometry is sane; it cannot tell you the
picture is wrong. Real examples from building this tool: an emitter produced
well-formed XML whose arrows were completely hidden behind their own labels, and
a bounds check reported every correct diagram as clipped. In both cases the
files were valid, the lint was clean, and the diagram was unusable. Look at the
PNG.

Cap vision rounds at two. If a diagram still fails after two rounds of fixes,
the problem is the diagram's scope, not its rendering — go back to the
`question:` and split it.
