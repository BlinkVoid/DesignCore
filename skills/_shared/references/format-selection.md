# Choosing a diagram format

A decision rubric, not a preference. One diagram has **one** format.

## Excalidraw — the default

Unless the diagram is going into a markdown file, this is the answer.

- The richest shape and boundary vocabulary of the three: rounded containers,
  dashed group enclosures, hachure fills, and arrows that follow the Graphviz
  splines around whatever sits between their endpoints.
- Reads as a designed diagram rather than an auto-generated one, without the
  model placing a single coordinate.

If you cannot articulate why another format is better, this is the answer.

## Mermaid — diagrams that live inside markdown

Choose it when the diagram is embedded in a `.md` file — a README, a design doc,
a PR description.

- Renders natively on GitHub, Obsidian, and Claude artifacts, so the diagram
  travels with the document instead of as a linked image.
- The source is text, so a reviewer sees what changed in the diff.

That is the whole of its case. "It's a flow chart" or "it's a sequence" is not a
reason — no emitter reads the spec's `kind`, and all three formats compile the
same graph.

## draw.io — a human will open and edit it

Choose it when someone will later hand-edit the diagram, or when it needs
branded cloud/network icons or multi-page drill-down. Mark it `hand_owned: true`
in the manifest once they have, or the next `render` overwrites their work.

## How the choice is recorded

`designcore render <id>` uses, in order:

1. `--format` if you pass it,
2. otherwise the format the manifest already records for that diagram,
3. otherwise `excalidraw`.

The choice is **sticky**: pass `--format mermaid` once and every later bare
`render` of that diagram stays mermaid. A diagram has exactly one manifest entry
and one format at a time, so switching format replaces the entry rather than
adding a second one.

`designcore new` takes only `--kind`; the format belongs to the render, not to
the spec.

**Switching format leaves the old files behind.** They are no longer referenced
by any entry, so `designcore check` reports them as `ORPHANED_ARTIFACT` — delete
them yourself. It reports and never deletes: removing a file a document may
still link to is your decision, not the tool's.
