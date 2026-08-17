---
name: flow-diagram
description: Use when documenting what a system does over time — a sequence of messages between participants, a state machine, or the steps and branches of a process. Produces a verified Mermaid diagram with a spec, a render, and a manifest entry in the project's docs/diagrams/.
---

# Flow Diagram

Draw what the system *does over time*: the order things happen in and where they can diverge.

## Before drawing

State the one question this diagram answers, in a sentence, in the spec's `question:` field.
If that sentence needs the word "and", you have two diagrams. Split them.

Pick the altitude and hold it:

- **sequence** — messages between participants, in order.
- **state** — the states a thing occupies and what moves it between them.
- **flow** — steps and branches in a process.

Discipline:

- Time flows one direction. Pick it and never reverse it mid-diagram.
- Every branch has an exit. A decision node with one outgoing edge is a bug in the diagram.
- Error paths are drawn, or the diagram states in its `question:` that it covers the happy path only.

## Procedure

Follow [../_shared/references/pipeline.md](../_shared/references/pipeline.md) exactly.
Judge the rendered PNG against [../_shared/references/legibility.md](../_shared/references/legibility.md).
Choose the format with [../_shared/references/format-selection.md](../_shared/references/format-selection.md);
flows default to Mermaid, which diffs cleanly and renders natively in repo docs.
Format mechanics: [../_shared/references/mermaid.md](../_shared/references/mermaid.md).

## Hard rules

- **Never write coordinates.** Geometry comes from the layout engine. A spec containing `x` or `y`
  is rejected by design.
- **Never report a diagram complete without a successful render.** If a backend is missing, say
  which one and how to install it.
- Label every edge whose meaning is not obvious from the nodes it joins.
