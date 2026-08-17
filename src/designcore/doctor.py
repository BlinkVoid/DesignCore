"""Report which external render backends are installed."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Backend:
    name: str
    command: str
    purpose: str
    install_hint: str


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
        purpose="Compute node geometry for Excalidraw diagrams",
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
)


def check_backends(which: Callable[[str], str | None] = shutil.which) -> list[BackendStatus]:
    """Probe each backend, returning availability without raising."""
    statuses = []
    for backend in BACKENDS:
        path = which(backend.command)
        statuses.append(BackendStatus(backend=backend, available=path is not None, path=path))
    return statuses
