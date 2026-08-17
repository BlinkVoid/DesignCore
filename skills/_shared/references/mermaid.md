# Mermaid mechanics

What `emit/mermaid.py` produces, and how to embed it.

## Generated syntax

A `flowchart <direction>` header, then nodes, edges, and class directives:

```
flowchart LR
    subgraph tier["Data Tier"]
        cdn["CDN"]
    end
    worker["API Worker"]
    cdn -->|cache miss| worker
    worker ==> db
    class worker primary
    classDef primary stroke-width:3px
    classDef muted opacity:0.55
```

- Nodes are always `id["label"]` boxes. Quotes in a label become `&quot;`.
- Groups become `subgraph <id>["<label>"] ... end`.
- Emphasis becomes `class <id> primary|muted` plus the matching `classDef`.

## Edge kinds

| spec `kind` | arrow |
|---|---|
| `sync` | `-->` |
| `async` | `-.->` |
| `data` | `==>` |
| `dashed` | `-.->` |

`async` and `dashed` render identically — Mermaid has no fifth arrow style. If
the distinction matters to the reader, carry it in the edge label instead.

Labelled edges render as `a -->|label| b`; unlabelled ones omit the pipes.

## Embedding

In markdown, embed the rendered SVG rather than the source when the diagram is
large or the renderer is uncertain:

```markdown
![Request flow](diagrams/out/mermaid/request-flow.svg)
```

For GitHub, Obsidian, or a Claude artifact, a fenced ```mermaid block
containing the `.mmd` contents renders natively and stays diffable. Either way,
record the containing document in the manifest's `embedded_in`.

## Rendering

`mmdc` drives a headless Chromium. DesignCore points it at a system browser so
the sandbox stays enabled; where no system browser exists it falls back to
`--no-sandbox`. Nothing to configure — but if a render fails with
"No usable sandbox", that is the mechanism involved.
