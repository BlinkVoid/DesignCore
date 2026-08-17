"""Export .drawio files with the draw.io CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from designcore.render import BackendMissing, RenderError

INSTALL_HINT = "sudo snap install drawio"


def _under_tmp(path: Path) -> bool:
    return Path(path).resolve().is_relative_to(Path("/tmp"))


def _command(source: Path, target: Path, fmt: str) -> list[str]:
    """Build the export command, prefixing xvfb-run when there is no display.

    The snap works headless but still needs an X server; `xvfb-run -a` supplies
    a throwaway one. When DISPLAY is already set we use it directly, which the
    Task 2 probe confirmed also works.
    """
    command = ["drawio", "-x", "-f", fmt, "-o", str(target), str(source)]
    if not os.environ.get("DISPLAY"):
        return ["xvfb-run", "-a", *command]
    return command


def render_drawio(
    source: Path,
    out_dir: Path,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> list[Path]:
    """Export a .drawio file to SVG and PNG. Returns the written paths."""
    if which("drawio") is None:
        raise BackendMissing(
            f"the draw.io CLI is not installed, so this diagram cannot be verified. "
            f"Install it with: {INSTALL_HINT}"
        )

    source, out_dir = Path(source), Path(out_dir)
    # Checked before rendering rather than after a confusing "file not found":
    # the drawio snap is strictly confined and gets its own private /tmp, so
    # host paths there are invisible to it (findings doc section 1).
    if _under_tmp(source) or _under_tmp(out_dir):
        raise RenderError(
            "the draw.io snap is strictly confined and cannot read /tmp; "
            f"move the diagram somewhere under {Path.home()} and retry "
            f"(source={source}, out_dir={out_dir})"
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    for fmt, suffix in (("svg", ".svg"), ("png", ".png")):
        target = out_dir / (source.stem + suffix)
        result = run(_command(source, target, fmt), capture_output=True, text=True)
        if result.returncode != 0:
            raise RenderError(f"drawio export failed for {source}: {result.stderr.strip()}")
        outputs.append(target)
    return outputs
