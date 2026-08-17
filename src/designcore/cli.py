"""designcore command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from designcore.doctor import check_backends
from designcore.lint import has_errors
from designcore.manifest import Manifest, check_manifest, load_manifest, save_manifest, upsert
from designcore.pipeline import GEOMETRY_FORMATS, Deps, compile_diagram, lint_diagram
from designcore.render import BackendMissing, RenderError
from designcore.spec import KINDS, SpecError, load_spec

FORMATS = ("mermaid", "drawio", "excalidraw")

# Amendment A23. There used to be a per-kind table here, but no emitter reads
# `spec.kind` -- a `sequence` spec compiles to the same box-and-arrow graph in
# all three formats, not to mermaid's native sequenceDiagram syntax -- so the
# table only ever encoded taste, and it spread one diagram across several
# formats by accident. One diagram has one format: excalidraw unless asked
# otherwise, and mermaid is asked for when the diagram is going into markdown.
DEFAULT_FORMAT = "excalidraw"


def _print_findings(findings) -> None:
    for finding in findings:
        marker = "ERROR " if finding.severity == "error" else "warn  "
        subject = f" [{finding.subject}]" if finding.subject else ""
        print(f"  {marker} {finding.code}{subject}: {finding.message}")


def _cmd_new(args: argparse.Namespace) -> int:
    root = Path(args.root)
    target = root / "src" / f"{args.id}.spec.yaml"
    if target.exists():
        print(f"{target} already exists")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    scaffold = {
        "id": args.id,
        "title": args.id.replace("-", " ").capitalize(),
        "kind": args.kind,
        "question": "REPLACE ME: the one question this diagram answers",
        "direction": "TB",
        "nodes": [],
        "edges": [],
        "groups": [],
    }
    target.write_text(yaml.safe_dump(scaffold, sort_keys=False), encoding="utf-8")
    # The default is the only honest answer here: a spec is format-agnostic by
    # design, and no manifest entry exists yet, so there is nowhere to record a
    # different choice. Pass --format to `render` instead; it sticks from then on.
    print(
        f"created {target} (renders as {DEFAULT_FORMAT}; "
        f"override with: designcore render {args.id} --format ...)"
    )
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    root = Path(args.root)
    spec = load_spec(root / "src" / f"{args.id}.spec.yaml")
    manifest_path = root / "diagrams.yaml"
    manifest = load_manifest(manifest_path) if manifest_path.exists() else Manifest(1, [])
    existing = next((d for d in manifest.diagrams if d.id == spec.id), None)
    # The choice is sticky: an explicit --format wins, otherwise the format this
    # diagram was last rendered as. Without that, a bare re-render would quietly
    # move a diagram back to the default and orphan the render it already had.
    fmt = args.format or (existing.format if existing else DEFAULT_FORMAT)

    entry = compile_diagram(
        spec, fmt, root, Deps.default(), hand_owned=bool(existing and existing.hand_owned)
    )
    save_manifest(upsert(manifest, entry), manifest_path)
    print(f"rendered {entry.id}: {', '.join(entry.rendered)}")
    return 0


def _recorded_format(root: Path, spec_id: str) -> str | None:
    """The format this diagram was last rendered as, per the manifest."""
    manifest_path = root / "diagrams.yaml"
    if not manifest_path.exists():
        return None
    return next((d.format for d in load_manifest(manifest_path).diagrams if d.id == spec_id), None)


def _rendered_svg(root: Path, spec_id: str) -> Path | None:
    """Locate a diagram's rendered SVG, which lives under out/<format>/.

    The manifest decides: since A23 a diagram holds one format, so the recorded
    entry names the render lint should be checking. The remaining fallbacks
    cover a diagram rendered before any entry was written -- previously this
    guessed among every format present, which meant lint could bounds-check one
    render and report the diagram clean while another sat clipped.
    """
    recorded = _recorded_format(root, spec_id)
    candidates = list(dict.fromkeys([*([recorded] if recorded else []), DEFAULT_FORMAT, *FORMATS]))

    for fmt in candidates:
        svg = root / "out" / fmt / f"{spec_id}.svg"
        if svg.exists():
            return svg
    return None


def _cmd_lint(args: argparse.Namespace) -> int:
    root = Path(args.root)
    spec = load_spec(root / "src" / f"{args.id}.spec.yaml")
    svg = _rendered_svg(root, args.id)
    # The render's own directory names its format (out/<format>/), which beats
    # inferring it from anywhere else.
    fmt = svg.parent.name if svg is not None else DEFAULT_FORMAT

    # Only lint placement geometry for formats that actually emit it; for
    # mermaid the layout is recomputed by the renderer, so check_svg_bounds
    # over the real SVG is the only meaningful geometry check.
    placements: dict = {}
    groups: dict = {}
    if spec.nodes and fmt in GEOMETRY_FORMATS:
        deps = Deps.default()
        placements = deps.layout(spec)
        groups = deps.layout_groups(spec)

    findings = lint_diagram(spec, placements, svg, groups=groups)
    if not findings:
        print(f"{args.id}: clean")
        return 0
    _print_findings(findings)
    return 1 if has_errors(findings) else 0


def _cmd_check(args: argparse.Namespace) -> int:
    findings = check_manifest(Path(args.root))
    if not findings:
        print("manifest: clean")
        return 0
    _print_findings(findings)
    return 1


def _cmd_doctor(_args: argparse.Namespace) -> int:
    missing = 0
    for status in check_backends():
        if status.available:
            print(f"  ok       {status.backend.name:<10} {status.path}")
        else:
            missing += 1
            print(f"  MISSING  {status.backend.name:<10} {status.backend.purpose}")
            print(f"           install: {status.backend.install_hint}")
    if missing:
        print(f"\n{missing} backend(s) missing. Diagrams cannot be verified without them.")
    return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="designcore")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_root(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--root", default="docs/diagrams", help="diagram root directory")

    new = subparsers.add_parser("new", help="Scaffold a diagram spec")
    new.add_argument("id")
    new.add_argument("--kind", required=True, choices=sorted(KINDS))
    add_root(new)
    new.set_defaults(func=_cmd_new)

    render = subparsers.add_parser("render", help="Compile and render a diagram")
    render.add_argument("id")
    render.add_argument("--format", choices=list(FORMATS))
    add_root(render)
    render.set_defaults(func=_cmd_render)

    lint = subparsers.add_parser("lint", help="Check a diagram spec and its render")
    lint.add_argument("id")
    add_root(lint)
    lint.set_defaults(func=_cmd_lint)

    check = subparsers.add_parser("check", help="Validate manifest integrity")
    add_root(check)
    check.set_defaults(func=_cmd_check)

    doctor = subparsers.add_parser("doctor", help="Report render backend availability")
    doctor.set_defaults(func=_cmd_doctor)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (BackendMissing, RenderError, SpecError, PermissionError) as error:
        # These carry the actionable text — the install command, the reason a
        # hand-owned file was not overwritten, the invalid field. A traceback
        # buries it.
        print(f"{error}")
        return 1
    except FileNotFoundError as error:
        print(f"not found: {error.filename or error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
