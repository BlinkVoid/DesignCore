"""Report which external render backends are installed."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from designcore.render.excalidraw import CHROME_CANDIDATES, HELPER_DIR


@dataclass(frozen=True)
class Backend:
    name: str
    command: str
    purpose: str
    install_hint: str
    # Other commands that satisfy this backend just as well.
    alternatives: tuple[str, ...] = ()
    # Set when the backend is a directory on disk rather than a program on
    # PATH, e.g. the export helper's installed node_modules.
    directory: Path | None = field(default=None)


@dataclass(frozen=True)
class BackendStatus:
    backend: Backend
    available: bool
    path: str | None


BACKENDS: tuple[Backend, ...] = (
    Backend(
        name="mermaid",
        command="mmdc",
        purpose="Render Mermaid sources to SVG and PNG",
        install_hint="npm install -g @mermaid-js/mermaid-cli",
    ),
    Backend(
        name="graphviz",
        command="dot",
        purpose="Compute node geometry for every format, and the geometry lint",
        install_hint="sudo apt install graphviz",
    ),
    Backend(
        name="drawio",
        command="drawio",
        purpose="Export .drawio files to SVG and PNG",
        install_hint="sudo snap install drawio",
    ),
    Backend(
        name="node",
        command="node",
        purpose="Run the Excalidraw SVG export helper (jsdom + @excalidraw/utils)",
        install_hint="install Node.js 20+ (nvm install --lts)",
    ),
    # Both of these are hard requirements of render_excalidraw. Without them
    # doctor would report all-ok on a machine where an excalidraw render
    # cannot run at all, which defeats its purpose as the pre-flight gate.
    Backend(
        name="chrome",
        command="google-chrome",
        alternatives=CHROME_CANDIDATES[1:],
        purpose="Rasterize Excalidraw SVG to PNG, and render Mermaid with the sandbox on",
        install_hint="install Google Chrome (https://google.com/chrome) or chromium",
    ),
    Backend(
        name="excalidraw-deps",
        command="",
        purpose="Excalidraw export helper dependencies (jsdom + @excalidraw/utils)",
        install_hint=f"npm install --prefix {HELPER_DIR}",
        directory=HELPER_DIR / "node_modules",
    ),
)


def check_backends(
    which: Callable[[str], str | None] = shutil.which,
    is_dir: Callable[[Path], bool] = Path.is_dir,
) -> list[BackendStatus]:
    """Probe each backend, returning availability without raising.

    `is_dir` is injected alongside `which` because not every backend is a
    program on PATH -- the export helper's dependencies are a directory.
    """
    statuses = []
    for backend in BACKENDS:
        if backend.directory is not None:
            found = str(backend.directory) if is_dir(backend.directory) else None
        else:
            found = next(
                (
                    located
                    for command in (backend.command, *backend.alternatives)
                    if (located := which(command))
                ),
                None,
            )
        statuses.append(BackendStatus(backend=backend, available=found is not None, path=found))
    return statuses
