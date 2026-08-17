# Choosing a diagram format

A decision rubric, not a preference. Pick by what the diagram is *for*.

## Mermaid — the default

Choose it for anything embedded in repo docs, reviewed in PRs, or under ~15 nodes.

- Renders natively on GitHub, Obsidian, and Claude artifacts.
- Diffs cleanly: the source is text, so a reviewer sees what changed.
- Costs least to produce and to regenerate.

If you cannot articulate why another format is better, this is the answer.

## draw.io — detailed architecture a human will edit

Choose it for detailed system architecture, branded cloud/network icons,
multi-page drill-down, or anything someone will later open and hand-edit.

## Excalidraw — deliberately informal

Choose it for concept sketches and teaching diagrams, where the hand-drawn look
signals "this is a mental model, not a spec". The informality is the message; do
not use it for anything a reader might mistake for authoritative.

## Default by kind

`designcore` picks a format from the spec's `kind` (this table is
`cli.DEFAULT_FORMAT` verbatim):

| kind | format |
|---|---|
| `context` | drawio |
| `container` | drawio |
| `deployment` | drawio |
| `network` | drawio |
| `sequence` | mermaid |
| `state` | mermaid |
| `flow` | mermaid |
| `concept` | excalidraw |

`--format` overrides it: `designcore render <id> --format mermaid`.

Renders are written to `out/<format>/`, so the same diagram can exist in more
than one format without one overwriting another. The manifest records the
format from the most recent render.
