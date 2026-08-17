"""Render Mermaid sources with mermaid-cli."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from designcore.render import BackendMissing, RenderError

INSTALL_HINT = "npm install -g @mermaid-js/mermaid-cli"

# Preferred first: a system browser ships a setuid sandbox helper and an
# AppArmor profile, so its sandbox still starts where the bundled one cannot.
CHROME_CANDIDATES = ("google-chrome", "chromium", "chromium-browser")

NO_SANDBOX_ARGS = ["--no-sandbox", "--disable-setuid-sandbox"]


def puppeteer_config(which: Callable[[str], str | None] = shutil.which) -> dict:
    """Launch options letting mermaid-cli's headless Chromium start on this machine.

    Puppeteer's bundled Chromium carries neither a setuid sandbox helper nor
    an AppArmor profile, so on distributions that restrict unprivileged user
    namespaces it aborts with "No usable sandbox!" before rendering anything.
    A system Chrome has both, so prefer it and keep the sandbox on. Only when
    no system browser exists do we fall back to disabling the sandbox, which
    is acceptable here because the rendered input is a diagram source this
    project generated, not untrusted web content.
    """
    for candidate in CHROME_CANDIDATES:
        executable = which(candidate)
        if executable:
            return {"executablePath": executable}
    return {"args": list(NO_SANDBOX_ARGS)}


def render_mermaid(
    source: Path,
    out_dir: Path,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> list[Path]:
    """Render a .mmd file to SVG and PNG. Returns the written paths."""
    if which("mmdc") is None:
        raise BackendMissing(
            f"mermaid-cli (mmdc) is not installed, so this diagram cannot be verified. "
            f"Install it with: {INSTALL_HINT}"
        )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", prefix="designcore-puppeteer-", delete=False, encoding="utf-8"
    ) as handle:
        json.dump(puppeteer_config(which), handle)
        config_path = Path(handle.name)

    try:
        outputs: list[Path] = []
        for suffix in (".svg", ".png"):
            target = out_dir / (Path(source).stem + suffix)
            result = run(
                [
                    "mmdc",
                    "-i", str(source),
                    "-o", str(target),
                    "-b", "transparent",
                    "-p", str(config_path),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RenderError(f"mmdc failed on {source}: {result.stderr.strip()}")
            outputs.append(target)
        return outputs
    finally:
        config_path.unlink(missing_ok=True)
