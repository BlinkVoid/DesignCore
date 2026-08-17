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
the format defaults to Excalidraw; ask for Mermaid when the diagram is going into a
markdown file, and draw.io when a human will hand-edit it or it needs branded icons.
Format mechanics: [../_shared/references/excalidraw.md](../_shared/references/excalidraw.md),
[../_shared/references/drawio.md](../_shared/references/drawio.md).

## Hard rules

- **Never write coordinates.** Geometry comes from the layout engine. A spec containing `x` or `y`
  is rejected by design.
- **Never report a diagram complete without a successful render.** If a backend is missing, say
  which one and how to install it.
- Name every boundary you draw. An unlabelled box group means nothing to a reader.
