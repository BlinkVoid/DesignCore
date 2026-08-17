"""designcore command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from designcore.doctor import check_backends
from designcore.lint import has_errors
from designcore.manifest import Manifest, check_manifest, load_manifest, save_manifest, upsert
from designcore.pipeline import Deps, compile_diagram, lint_diagram
from designcore.spec import load_spec

DEFAULT_FORMAT = {
    "context": "drawio", "container": "drawio", "deployment": "drawio", "network": "drawio",
    "sequence": "mermaid", "state": "mermaid", "flow": "mermaid", "concept": "excalidraw",
}


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
    fmt = args.format or DEFAULT_FORMAT[args.kind]
    print(f"created {target} (format: {fmt})")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    root = Path(args.root)
    spec = load_spec(root / "src" / f"{args.id}.spec.yaml")
    fmt = args.format or DEFAULT_FORMAT[spec.kind]
    manifest_path = root / "diagrams.yaml"
    manifest = load_manifest(manifest_path) if manifest_path.exists() else Manifest(1, [])
    existing = next((d for d in manifest.diagrams if d.id == spec.id), None)

    entry = compile_diagram(
        spec, fmt, root, Deps.default(), hand_owned=bool(existing and existing.hand_owned)
    )
    save_manifest(upsert(manifest, entry), manifest_path)
    print(f"rendered {entry.id}: {', '.join(entry.rendered)}")
    return 0


def _rendered_svg(root: Path, spec_id: str, kind: str) -> Path | None:
    """Locate a diagram's rendered SVG, which lives under out/<format>/.

    Prefers the format the manifest records; falls back to the kind's default
    and then to any format present, so lint still inspects the render after a
    format change.
    """
    manifest_path = root / "diagrams.yaml"
    candidates: list[str] = []
    if manifest_path.exists():
        entry = next(
            (d for d in load_manifest(manifest_path).diagrams if d.id == spec_id), None
        )
        if entry is not None:
            candidates.append(entry.format)
    candidates.append(DEFAULT_FORMAT[kind])
    candidates.extend(f for f in DEFAULT_FORMAT.values() if f not in candidates)

    for fmt in candidates:
        svg = root / "out" / fmt / f"{spec_id}.svg"
        if svg.exists():
            return svg
    return None


def _cmd_lint(args: argparse.Namespace) -> int:
    root = Path(args.root)
    spec = load_spec(root / "src" / f"{args.id}.spec.yaml")
    placements = Deps.default().layout(spec) if spec.nodes else {}
    findings = lint_diagram(spec, placements, _rendered_svg(root, args.id, spec.kind))
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
    new.add_argument("--kind", required=True, choices=sorted(DEFAULT_FORMAT))
    new.add_argument("--format", choices=["mermaid", "drawio", "excalidraw"])
    add_root(new)
    new.set_defaults(func=_cmd_new)

    render = subparsers.add_parser("render", help="Compile and render a diagram")
    render.add_argument("id")
    render.add_argument("--format", choices=["mermaid", "drawio", "excalidraw"])
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
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
