"""Render .excalidraw documents to SVG, then rasterize to PNG.

No published CLI renders Excalidraw scenes, so DesignCore ships a small Node
helper (`js/render.mjs`) that installs the jsdom shim recorded in the findings
doc section 3 before importing `@excalidraw/utils`. PNG comes from headless
Chrome rasterizing the SVG the helper produced (amendment A3).
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree

from designcore.render import BackendMissing, RenderError

HELPER_DIR = Path(__file__).parent / "js"
NODE_HINT = "install Node.js 20+ (nvm install --lts)"
CHROME_CANDIDATES = ("google-chrome", "chromium", "chromium-browser")
CHROME_HINT = "install Google Chrome (https://google.com/chrome) or chromium"


DEFAULT_VIEWPORT = (1200, 800)


def _svg_size(svg: Path) -> tuple[int, int]:
    """Read the SVG's own dimensions so the screenshot is not mostly blank.

    Chrome's default viewport dwarfs a typical diagram, and the empty canvas
    is dead weight in the vision pass. Falls back to a sane default if the
    document does not declare a size.
    """
    try:
        root = ElementTree.parse(svg).getroot()
    except ElementTree.ParseError:
        return DEFAULT_VIEWPORT

    def _dimension(name: str, index: int) -> int | None:
        raw = root.get(name)
        if raw:
            try:
                return math.ceil(float(raw.rstrip("px")))
            except ValueError:
                pass
        view_box = root.get("viewBox")
        if view_box:
            parts = view_box.replace(",", " ").split()
            if len(parts) == 4:
                try:
                    return math.ceil(float(parts[2 + index]))
                except ValueError:
                    pass
        return None

    width = _dimension("width", 0) or DEFAULT_VIEWPORT[0]
    height = _dimension("height", 1) or DEFAULT_VIEWPORT[1]
    return width, height


def render_excalidraw(
    source: Path,
    out_dir: Path,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
    helper_dir: Path = HELPER_DIR,
) -> list[Path]:
    """Render an .excalidraw file to SVG and PNG. Returns the written paths."""
    helper_dir = Path(helper_dir)
    if not (helper_dir / "node_modules").is_dir():
        raise BackendMissing(
            "the Excalidraw export helper's dependencies are not installed, so this "
            "diagram cannot be verified. Install them with: "
            f"npm install --prefix {helper_dir}"
        )
    if which("node") is None:
        raise BackendMissing(
            f"Node.js is required to run the Excalidraw export helper; {NODE_HINT}"
        )
    chrome = next((which(c) for c in CHROME_CANDIDATES if which(c)), None)
    if chrome is None:
        raise BackendMissing(
            f"a headless chrome is required to rasterize Excalidraw SVG; {CHROME_HINT}"
        )

    source, out_dir = Path(source), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    svg = out_dir / (source.stem + ".svg")
    png = out_dir / (source.stem + ".png")

    # Only the exit status decides success. The shim reliably warns
    # "Couldn't transform font-face to css" on stderr; text still renders.
    result = run(
        ["node", str(helper_dir / "render.mjs"), str(source), str(svg)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RenderError(f"excalidraw export failed for {source}: {result.stderr.strip()}")

    width, height = _svg_size(svg)
    result = run(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--default-background-color=00000000",
            f"--window-size={width},{height}",
            f"--screenshot={png}",
            str(svg),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RenderError(f"chrome failed to rasterize {svg}: {result.stderr.strip()}")

    return [svg, png]
