import subprocess
import uuid
from pathlib import Path

import pytest

from designcore.render import BackendMissing, RenderError
from designcore.render.drawio import render_drawio
from designcore.render.excalidraw import render_excalidraw


@pytest.fixture
def scratch():
    """A working directory outside /tmp.

    The draw.io snap is strictly confined and cannot see the host's /tmp, so
    pytest's tmp_path is unusable for anything touching that backend
    (amendment A3).
    """
    path = Path.home() / ".cache" / "designcore-tests" / uuid.uuid4().hex
    path.mkdir(parents=True)
    yield path
    for child in sorted(path.rglob("*"), reverse=True):
        child.rmdir() if child.is_dir() else child.unlink()
    path.rmdir()


def _ok(cmd, **kwargs):
    Path(cmd[cmd.index("-o") + 1]).write_text("rendered", encoding="utf-8")
    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def test_drawio_missing_backend_names_the_install_command(tmp_path):
    src = tmp_path / "d.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")
    with pytest.raises(BackendMissing, match="snap install drawio"):
        render_drawio(src, tmp_path / "out", run=_ok, which=lambda c: None)


def test_drawio_renders_svg_and_png(scratch):
    src = scratch / "d.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")
    outputs = render_drawio(src, scratch / "out", run=_ok, which=lambda c: "/snap/bin/drawio")
    assert [p.suffix for p in outputs] == [".svg", ".png"]
    assert all(p.exists() for p in outputs)


def test_drawio_nonzero_exit_raises_render_error(scratch):
    src = scratch / "d.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")

    def fail(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="cannot open display")

    with pytest.raises(RenderError, match="cannot open display"):
        render_drawio(src, scratch / "out", run=fail, which=lambda c: "/snap/bin/drawio")


def test_drawio_rejects_tmp_paths_that_the_snap_cannot_see(tmp_path):
    """Amendment A3: strict snap confinement gives drawio a private /tmp."""
    src = tmp_path / "d.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")
    with pytest.raises(RenderError, match="snap"):
        render_drawio(src, tmp_path / "out", run=_ok, which=lambda c: "/snap/bin/drawio")


def test_drawio_prefixes_xvfb_when_display_is_unset(scratch, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    src = scratch / "d.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")
    seen: list[list[str]] = []

    def capture(cmd, **kwargs):
        seen.append(cmd)
        return _ok(cmd, **kwargs)

    render_drawio(src, scratch / "out", run=capture, which=lambda c: "/snap/bin/drawio")
    assert seen[0][:2] == ["xvfb-run", "-a"]


def test_drawio_does_not_prefix_xvfb_when_display_is_set(scratch, monkeypatch):
    monkeypatch.setenv("DISPLAY", ":1")
    src = scratch / "d.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")
    seen: list[list[str]] = []

    def capture(cmd, **kwargs):
        seen.append(cmd)
        return _ok(cmd, **kwargs)

    render_drawio(src, scratch / "out", run=capture, which=lambda c: "/snap/bin/drawio")
    assert seen[0][0] == "drawio"


# --- excalidraw -----------------------------------------------------------


def _excalidraw_ok(cmd, **kwargs):
    """Fake both hops: the node helper writes the SVG, chrome writes the PNG."""
    if cmd[0] == "node":
        Path(cmd[3]).write_text("<svg/>", encoding="utf-8")  # node <helper> <src> <target>
    else:
        target = next(a.split("=", 1)[1] for a in cmd if a.startswith("--screenshot="))
        Path(target).write_text("png", encoding="utf-8")
    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def _helper(tmp_path: Path) -> Path:
    """A helper directory that looks installed."""
    (tmp_path / "js" / "node_modules").mkdir(parents=True)
    return tmp_path / "js"


def test_excalidraw_without_node_modules_names_the_install_command(tmp_path):
    src = tmp_path / "d.excalidraw"
    src.write_text("{}", encoding="utf-8")
    with pytest.raises(BackendMissing, match="npm install"):
        render_excalidraw(
            src, tmp_path / "out", run=_excalidraw_ok,
            which=lambda c: f"/usr/bin/{c}", helper_dir=tmp_path / "js",
        )


def test_excalidraw_without_node_names_the_install_command(tmp_path):
    src = tmp_path / "d.excalidraw"
    src.write_text("{}", encoding="utf-8")
    with pytest.raises(BackendMissing, match="[Nn]ode"):
        render_excalidraw(
            src, tmp_path / "out", run=_excalidraw_ok,
            which=lambda c: None if c == "node" else f"/usr/bin/{c}",
            helper_dir=_helper(tmp_path),
        )


def test_excalidraw_without_chrome_names_the_install_command(tmp_path):
    src = tmp_path / "d.excalidraw"
    src.write_text("{}", encoding="utf-8")
    with pytest.raises(BackendMissing, match="chrome"):
        render_excalidraw(
            src, tmp_path / "out", run=_excalidraw_ok,
            which=lambda c: "/usr/bin/node" if c == "node" else None,
            helper_dir=_helper(tmp_path),
        )


def test_excalidraw_renders_svg_and_png(tmp_path):
    src = tmp_path / "d.excalidraw"
    src.write_text("{}", encoding="utf-8")
    outputs = render_excalidraw(
        src, tmp_path / "out", run=_excalidraw_ok,
        which=lambda c: f"/usr/bin/{c}", helper_dir=_helper(tmp_path),
    )
    assert [p.suffix for p in outputs] == [".svg", ".png"]
    assert all(p.exists() for p in outputs)


def test_excalidraw_nonzero_exit_raises_render_error(tmp_path):
    src = tmp_path / "d.excalidraw"
    src.write_text("{}", encoding="utf-8")

    def fail(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="TypeError in shim")

    with pytest.raises(RenderError, match="TypeError in shim"):
        render_excalidraw(
            src, tmp_path / "out", run=fail,
            which=lambda c: f"/usr/bin/{c}", helper_dir=_helper(tmp_path),
        )


def test_excalidraw_png_viewport_matches_the_svg(tmp_path):
    """Chrome's default viewport is far larger than a diagram, so an unsized
    screenshot is mostly empty canvas -- wasted budget in the vision pass."""
    src = tmp_path / "d.excalidraw"
    src.write_text("{}", encoding="utf-8")
    seen: list[list[str]] = []

    def capture(cmd, **kwargs):
        if cmd[0] == "node":
            Path(cmd[3]).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="311.5" height="58">'
                "</svg>",
                encoding="utf-8",
            )
        else:
            seen.append(cmd)
            target = next(a.split("=", 1)[1] for a in cmd if a.startswith("--screenshot="))
            Path(target).write_text("png", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    render_excalidraw(
        src, tmp_path / "out", run=capture,
        which=lambda c: f"/usr/bin/{c}", helper_dir=_helper(tmp_path),
    )
    assert "--window-size=312,58" in seen[0]


def test_excalidraw_font_warning_on_stderr_is_not_a_failure(tmp_path):
    """The jsdom shim always warns about font-face; exit status is what counts.

    Recorded in the findings doc as a known non-fatal condition (Task 9).
    """
    src = tmp_path / "d.excalidraw"
    src.write_text("{}", encoding="utf-8")

    def warn(cmd, **kwargs):
        result = _excalidraw_ok(cmd, **kwargs)
        return subprocess.CompletedProcess(
            cmd, 0, stdout="", stderr='Couldn\'t transform font-face to css for family "undefined"'
        )

    outputs = render_excalidraw(
        src, tmp_path / "out", run=warn,
        which=lambda c: f"/usr/bin/{c}", helper_dir=_helper(tmp_path),
    )
    assert len(outputs) == 2
