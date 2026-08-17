"""Geometry checks over placements and rendered SVG."""

from __future__ import annotations

import math
import re
from itertools import combinations
from pathlib import Path
from xml.etree import ElementTree

from designcore.layout import Placement
from designcore.lint import Finding

SVG_NS = "{http://www.w3.org/2000/svg}"

# Elements whose x/y/width/height define a box worth bounds-checking.
# foreignObject matters as much as rect: mermaid renders its labels into
# foreignObject rather than <text>, so omitting it blinds the check to
# exactly the truncated labels it exists to catch.
BOXED_TAGS = (f"{SVG_NS}rect", f"{SVG_NS}foreignObject", f"{SVG_NS}image")

# Sub-pixel overhang is rounding, not visible clipping.
EPSILON = 0.5

# An affine transform as (a, b, c, d, e, f), matching SVG's matrix() order.
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

_TRANSFORM_RE = re.compile(r"(\w+)\s*\(([^)]*)\)")


def _overlaps(a: Placement, b: Placement) -> bool:
    return (
        a.x + EPSILON < b.x + b.width
        and b.x + EPSILON < a.x + a.width
        and a.y + EPSILON < b.y + b.height
        and b.y + EPSILON < a.y + a.height
    )


def check_geometry(
    placements: list[Placement], canvas: tuple[float, float] | None = None
) -> list[Finding]:
    findings: list[Finding] = []

    for a, b in combinations(placements, 2):
        if _overlaps(a, b):
            findings.append(
                Finding(
                    code="NODE_OVERLAP",
                    severity="error",
                    message=f"nodes {a.id!r} and {b.id!r} overlap",
                    subject=f"{a.id},{b.id}",
                )
            )

    for box in placements:
        # Graphviz reports node centres, so x = cx - width/2 lands a fraction
        # either side of zero. Without tolerance a node flush with the canvas
        # edge (x=-0.001) is reported off-canvas and fails a correct diagram.
        outside = box.x < -EPSILON or box.y < -EPSILON
        if canvas is not None:
            width, height = canvas
            outside = (
                outside
                or box.x + box.width > width + EPSILON
                or box.y + box.height > height + EPSILON
            )
        if outside:
            findings.append(
                Finding(
                    code="OFF_CANVAS",
                    severity="error",
                    message=f"node {box.id!r} falls outside the canvas",
                    subject=box.id,
                )
            )

    return findings


def _multiply(m: tuple, n: tuple) -> tuple:
    """Compose two affine transforms, applying *n* inside *m*."""
    a1, b1, c1, d1, e1, f1 = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _parse_transform(value: str) -> tuple | None:
    """Parse an SVG transform list. Returns None if any part is unsupported.

    Refusing to guess matters: a transform we cannot model would make every
    bound derived from it fiction, so the caller skips that subtree instead.
    """
    matrix = IDENTITY
    for name, raw_args in _TRANSFORM_RE.findall(value):
        try:
            args = [float(a) for a in raw_args.replace(",", " ").split()]
        except ValueError:
            return None
        if name == "translate" and len(args) in (1, 2):
            tx, ty = args[0], (args[1] if len(args) > 1 else 0.0)
            step = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif name == "scale" and len(args) in (1, 2):
            sx, sy = args[0], (args[1] if len(args) > 1 else args[0])
            step = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif name == "matrix" and len(args) == 6:
            step = tuple(args)
        elif name == "rotate" and len(args) in (1, 3):
            angle = math.radians(args[0])
            cos, sin = math.cos(angle), math.sin(angle)
            step = (cos, sin, -sin, cos, 0.0, 0.0)
            if len(args) == 3:
                cx, cy = args[1], args[2]
                step = _multiply(
                    _multiply((1.0, 0.0, 0.0, 1.0, cx, cy), step),
                    (1.0, 0.0, 0.0, 1.0, -cx, -cy),
                )
        else:
            return None  # skew or anything else: cannot reason soundly
        matrix = _multiply(matrix, step)
    return matrix


def _local_box(element) -> tuple[float, float, float, float] | None:
    if element.tag not in BOXED_TAGS:
        return None
    try:
        x = float(element.get("x", 0))
        y = float(element.get("y", 0))
        w = float(element.get("width", 0))
        h = float(element.get("height", 0))
    except (TypeError, ValueError):
        return None  # percentages and other non-user-unit values
    return x, y, x + w, y + h


def _transformed_bounds(matrix: tuple, box: tuple) -> tuple[float, float, float, float]:
    """Map a local box to root coordinates via its four corners (rotation-safe)."""
    a, b, c, d, e, f = matrix
    x0, y0, x1, y1 = box
    points = [
        (a * px + c * py + e, b * px + d * py + f)
        for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))
    ]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def check_svg_bounds(svg_path: Path) -> list[Finding]:
    """Flag rendered content that extends past the viewBox, i.e. clipped output.

    Coordinates are resolved through the accumulated transform of every
    ancestor before being compared. Raw attribute values are meaningless on
    their own -- mermaid centres each shape on its own translate origin, so
    judging them untransformed reports clipping on every correct diagram.
    """
    root = ElementTree.parse(svg_path).getroot()
    view_box = root.get("viewBox")
    if not view_box:
        return []
    min_x, min_y, width, height = (float(v) for v in view_box.replace(",", " ").split())
    max_x, max_y = min_x + width, min_y + height

    stack = [(root, IDENTITY)]
    while stack:
        element, matrix = stack.pop()
        transform = element.get("transform")
        if transform:
            step = _parse_transform(transform)
            if step is None:
                continue  # unsupported transform: skip this subtree
            matrix = _multiply(matrix, step)

        box = _local_box(element)
        if box is not None:
            x0, y0, x1, y1 = _transformed_bounds(matrix, box)
            if (
                x0 < min_x - EPSILON
                or y0 < min_y - EPSILON
                or x1 > max_x + EPSILON
                or y1 > max_y + EPSILON
            ):
                return [
                    Finding(
                        code="CLIPPED_CONTENT",
                        severity="error",
                        message=f"rendered content extends past the viewBox in {svg_path.name}",
                        subject=svg_path.name,
                    )
                ]

        stack.extend((child, matrix) for child in element)
    return []
