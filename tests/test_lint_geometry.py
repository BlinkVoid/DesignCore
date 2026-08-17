from designcore.layout import Placement
from designcore.lint.geometry import check_geometry, check_svg_bounds


def test_separated_boxes_are_clean():
    boxes = [Placement("a", 0, 0, 100, 50), Placement("b", 150, 0, 100, 50)]
    assert check_geometry(boxes) == []


def test_overlapping_boxes_are_an_error():
    boxes = [Placement("a", 0, 0, 100, 50), Placement("b", 50, 10, 100, 50)]
    findings = check_geometry(boxes)
    assert [f.code for f in findings] == ["NODE_OVERLAP"]
    assert findings[0].severity == "error"
    assert "a" in findings[0].subject and "b" in findings[0].subject


def test_touching_edges_do_not_count_as_overlap():
    boxes = [Placement("a", 0, 0, 100, 50), Placement("b", 100, 0, 100, 50)]
    assert check_geometry(boxes) == []


def test_negative_coordinates_are_off_canvas():
    findings = check_geometry([Placement("a", -10, 0, 100, 50)])
    assert [f.code for f in findings] == ["OFF_CANVAS"]


def test_box_beyond_declared_canvas_is_off_canvas():
    findings = check_geometry([Placement("a", 0, 0, 100, 50)], canvas=(80, 200))
    assert [f.code for f in findings] == ["OFF_CANVAS"]


def test_svg_within_viewbox_is_clean(tmp_path):
    svg = tmp_path / "ok.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
        '<rect x="10" y="10" width="100" height="50"/></svg>',
        encoding="utf-8",
    )
    assert check_svg_bounds(svg) == []


def test_svg_content_outside_viewbox_is_clipped(tmp_path):
    svg = tmp_path / "clipped.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect x="10" y="10" width="200" height="50"/></svg>',
        encoding="utf-8",
    )
    findings = check_svg_bounds(svg)
    assert [f.code for f in findings] == ["CLIPPED_CONTENT"]
    assert findings[0].severity == "error"


def _svg(tmp_path, body: str, view_box: str = "0 0 200 100"):
    path = tmp_path / "t.svg"
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}">{body}</svg>',
        encoding="utf-8",
    )
    return path


def test_negative_local_coordinates_inside_after_translate_are_clean(tmp_path):
    """Mermaid centres shapes on their translate origin, so local x is always
    negative. Judging raw coordinates flags every correct diagram."""
    svg = _svg(tmp_path, '<g transform="translate(50,50)"><rect x="-20" y="-20" width="40" height="40"/></g>')
    assert check_svg_bounds(svg) == []


def test_positive_local_coordinates_pushed_outside_by_translate_are_clipped(tmp_path):
    svg = _svg(tmp_path, '<g transform="translate(170,0)"><rect x="10" y="10" width="50" height="50"/></g>')
    assert [f.code for f in check_svg_bounds(svg)] == ["CLIPPED_CONTENT"]


def test_nested_transforms_compose(tmp_path):
    svg = _svg(
        tmp_path,
        '<g transform="translate(100,20)"><g transform="translate(-90,-10)">'
        '<rect x="0" y="0" width="40" height="40"/></g></g>',
    )
    assert check_svg_bounds(svg) == []


def test_scale_is_applied(tmp_path):
    svg = _svg(tmp_path, '<g transform="scale(4)"><rect x="10" y="10" width="40" height="40"/></g>')
    assert [f.code for f in check_svg_bounds(svg)] == ["CLIPPED_CONTENT"]


def test_foreign_object_bounds_are_checked(tmp_path):
    """Mermaid renders labels into foreignObject, not <text>; ignoring it means
    the check cannot see the truncated labels it exists to catch."""
    svg = _svg(tmp_path, '<foreignObject x="180" y="10" width="60" height="20"/>')
    assert [f.code for f in check_svg_bounds(svg)] == ["CLIPPED_CONTENT"]


def test_unparseable_transform_is_skipped_rather_than_guessed(tmp_path):
    svg = _svg(tmp_path, '<g transform="skewX(30)"><rect x="-500" y="-500" width="40" height="40"/></g>')
    assert check_svg_bounds(svg) == []


def test_real_mermaid_output_structure_is_clean(tmp_path):
    """Shape taken from actual mmdc output (see Task 6 render probe)."""
    svg = _svg(
        tmp_path,
        '<g transform="translate(43.3359375, 35)">'
        '<rect x="-35.3359375" y="-27" width="70.671875" height="54"/>'
        '<g transform="translate(-5.3359375, -12)">'
        '<foreignObject width="10.671875" height="24"/></g></g>'
        '<g transform="translate(164.0078125, 35)">'
        '<rect x="-35.3359375" y="-27" width="70.671875" height="54"/></g>',
        view_box="0 0 207.34375 70",
    )
    assert check_svg_bounds(svg) == []


def test_subpixel_negative_coordinate_is_not_off_canvas():
    """Graphviz reports centres, so x = cx - width/2 accumulates float error.

    A node flush with the canvas edge comes back as x=-0.001 and must not be
    reported as off-canvas -- that fails the pipeline on a correct diagram.
    """
    assert check_geometry([Placement("a", -0.001, 0.0, 92.0, 36.0)]) == []


def test_a_real_negative_coordinate_is_still_off_canvas():
    assert [f.code for f in check_geometry([Placement("a", -5, 0, 92, 36)])] == ["OFF_CANVAS"]


def test_subpixel_canvas_overflow_is_tolerated():
    findings = check_geometry([Placement("a", 0, 0, 100.002, 50)], canvas=(100, 200))
    assert findings == []


def test_subpixel_overlap_is_not_an_overlap():
    boxes = [Placement("a", 0, 0, 100.001, 50), Placement("b", 100, 0, 100, 50)]
    assert check_geometry(boxes) == []
