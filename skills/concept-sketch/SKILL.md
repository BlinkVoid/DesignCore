---
name: concept-sketch
description: Use when explaining a mental model rather than documenting a system — teaching diagrams, whiteboard-style sketches, and the idea behind a design. Produces a verified Excalidraw sketch with a spec, a render, and a manifest entry in the project's docs/diagrams/.
---

# Concept Sketch

Draw a *mental model*: the idea behind the system, not its literal structure.

## Before drawing

State the one question this sketch answers, in a sentence, in the spec's `question:` field.
If that sentence needs the word "and", you have two sketches. Split them.

Discipline:

- Annotation over precision. A sketch that explains beats a schematic that documents.
- Deliberate informality signals "this is a model, not a spec" — that signal is the point.
- If a reader could mistake the sketch for the real topology, use architecture-diagram instead.

## Procedure

Follow [../_shared/references/pipeline.md](../_shared/references/pipeline.md) exactly.
Judge the rendered PNG against [../_shared/references/legibility.md](../_shared/references/legibility.md).
Choose the format with [../_shared/references/format-selection.md](../_shared/references/format-selection.md);
the format defaults to Excalidraw, which is what a sketch wants anyway; ask for Mermaid
only when the sketch is going into a markdown file.
Format mechanics: [../_shared/references/excalidraw.md](../_shared/references/excalidraw.md).

## Render status

Excalidraw sketches are **render-verified**: the renderer runs a Node helper shipped with
DesignCore (jsdom shim plus `@excalidraw/utils`), then rasterizes to PNG with headless Chrome,
so step 4 of the pipeline judges a real picture. The render proves the picture exists and is
inspectable — whether it *reads* well stays a human judgment, same as every format. Status
and history: `docs/plans/2026-08-16-render-backend-findings.md` section 3.

Two expected conditions, neither a failure:

- The export logs `Couldn't transform font-face to css for family "undefined"` and text falls
  back to a system font. Geometry and content are unaffected.
- If the helper's dependencies are not installed, the renderer raises `BackendMissing` naming the
  exact `npm install --prefix ...` command. Report that and stop — **do not** describe the sketch
  as complete or claim it was visually checked when it was not rendered.

## Hard rules

- **Never write coordinates.** Geometry comes from the layout engine, even here — the hand-drawn
  look is Excalidraw's rendering, not placement by hand. A spec containing `x` or `y` is rejected
  by design.
- **Never report a sketch complete without a successful render.** If a backend is missing, say
  which one and how to install it.
- Informality is a deliberate signal, not an excuse for an unreadable sketch. It still has to pass
  the legibility rules.
