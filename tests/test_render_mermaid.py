import json
import subprocess
from pathlib import Path

import pytest

from designcore.render import BackendMissing, RenderError
from designcore.render.mermaid import puppeteer_config, render_mermaid


def _ok(cmd, **kwargs):
    Path(cmd[cmd.index("-o") + 1]).write_text("rendered", encoding="utf-8")
    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def test_raises_backend_missing_with_install_hint(tmp_path):
    src = tmp_path / "d.mmd"
    src.write_text("flowchart LR\n  a --> b\n", encoding="utf-8")
    with pytest.raises(BackendMissing, match="mermaid-cli"):
        render_mermaid(src, tmp_path / "out", run=_ok, which=lambda c: None)


def test_renders_svg_and_png(tmp_path):
    src = tmp_path / "d.mmd"
    src.write_text("flowchart LR\n  a --> b\n", encoding="utf-8")
    outputs = render_mermaid(src, tmp_path / "out", run=_ok, which=lambda c: "/usr/bin/mmdc")
    assert [p.suffix for p in outputs] == [".svg", ".png"]
    assert all(p.exists() for p in outputs)


def test_raises_render_error_on_nonzero_exit(tmp_path):
    src = tmp_path / "d.mmd"
    src.write_text("not mermaid at all", encoding="utf-8")

    def fail(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Parse error on line 1")

    with pytest.raises(RenderError, match="Parse error"):
        render_mermaid(src, tmp_path / "out", run=fail, which=lambda c: "/usr/bin/mmdc")


def test_prefers_system_chrome_so_the_sandbox_stays_on():
    config = puppeteer_config(
        which=lambda c: "/usr/bin/google-chrome" if c == "google-chrome" else None
    )
    assert config == {"executablePath": "/usr/bin/google-chrome"}


def test_falls_back_to_no_sandbox_when_no_system_browser_exists():
    config = puppeteer_config(which=lambda c: None)
    assert config == {"args": ["--no-sandbox", "--disable-setuid-sandbox"]}


def test_passes_the_puppeteer_config_to_mmdc(tmp_path):
    src = tmp_path / "d.mmd"
    src.write_text("flowchart LR\n  a --> b\n", encoding="utf-8")
    seen: list[dict] = []

    def capture(cmd, **kwargs):
        seen.append(json.loads(Path(cmd[cmd.index("-p") + 1]).read_text(encoding="utf-8")))
        return _ok(cmd, **kwargs)

    render_mermaid(src, tmp_path / "out", run=capture, which=lambda c: f"/usr/bin/{c}")
    assert seen == [{"executablePath": "/usr/bin/google-chrome"}] * 2


def test_temporary_puppeteer_config_is_cleaned_up(tmp_path):
    src = tmp_path / "d.mmd"
    src.write_text("flowchart LR\n  a --> b\n", encoding="utf-8")
    configs: list[Path] = []

    def capture(cmd, **kwargs):
        configs.append(Path(cmd[cmd.index("-p") + 1]))
        return _ok(cmd, **kwargs)

    render_mermaid(src, tmp_path / "out", run=capture, which=lambda c: f"/usr/bin/{c}")
    assert configs and not [p for p in configs if p.exists()]
