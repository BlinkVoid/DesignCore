# DesignCore Release Roadmap

> **For agentic workers:** Roadmap-level plan. Each task is executed with tests
> and commits; functional changes update ARCHITECTURE.md / specs in the same commit.

**Goal:** Take DesignCore from private WIP to a public tagged 0.1 release with a
landing page, mirroring the GearCore release process.

**Architecture:** No architectural changes. All work is packaging, docs, example
integrity, and distribution. One optional tooling addition (`doctor --deep`).

## Global Constraints

- Python >=3.11 floor unchanged; runtime deps stay minimal
- The two rules stay intact: model never writes coordinates; no diagram without a render
- Every workstream ends green: `uv run pytest -q` and `uv run designcore check --root examples/docs/diagrams`

---

## Workstream A — Public release prep

### Task A1: License and packaging metadata
- [ ] Add MIT `LICENSE` file
- [ ] `pyproject.toml`: `license`, `readme`, classifiers, keywords, URLs
- [ ] README: license badge, install-from-GitHub path (`uv tool install git+...`)
- Closes: act_54dcfa0a32e54137

### Task A2: Fix the stale shipped example
- [ ] Re-render `designcore-pipeline` in `examples/docs/diagrams`
- [ ] Commit regenerated SVG/PNG + manifest so fresh clones pass `designcore check`
- [ ] Verify: fresh clone simulation (`git clone` to /tmp, run check)
- Closes: act_25fd01cffd104abc

### Task A3: Scope the word "verified" honestly
- [ ] README + skills references: verified = *rendered successfully + deterministic
      structural/density/geometry checks pass*. NOT visual correctness or comprehension.
- [ ] Add one-line caveat where "verified" first appears
- Closes: act_16c54fdf9ea449c0

### Task A4: Portability audit documentation
- [ ] Turn the existing render-backend-findings into a README "Requirements" table:
      per-backend what it does, how to install, known platform caveats
      (AppArmor/chromium sandbox note, snap drawio, local-extract graphviz fallback)
- [ ] `doctor` already names install commands — verify each command string is accurate
- Closes: act_2992239fbee64a8f (documentation half; cross-platform CI is out of scope for 0.1)

### Task A5: Publish
- [ ] Push main (incl. 4d9a00c)
- [ ] Make repo public (owner decision — confirm before flipping)
- [ ] Tag `v0.1.0` + GitHub release with notes
- Closes: act_cf5c91ca89e145b4, act_cc9aca0ee3da4a0a

---

## Workstream B — Web presence & SEO

### Task B1: Landing page
- [ ] `site/index.html`: hero ("diagrams your agent can prove rendered"), the two rules,
      pipeline diagram, format table, install, skills list; meta/OG/JSON-LD `SoftwareApplication`
- [ ] `.github/workflows/deploy-pages.yml` (same pattern as GearCore, `enablement: true`)
- [ ] Enable Pages, verify deployment returns 200

### Task B2: Repo presentation
- [ ] Description, homepage URL → Pages site, topics (diagrams, graphviz, mermaid,
      excalidraw, drawio, mcp, ai-tools, ...)
- [ ] README link to website

---

## Deferred (recorded, not scheduled)

- `designcore doctor --deep` (trivial render per backend) — act_b31388b1c91e4d5c
- Cross-platform CI matrix (ubuntu/macos) — after 0.1 feedback
