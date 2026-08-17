import shutil
from pathlib import Path

import pytest

from designcore.cli import main

EXAMPLE = Path("examples/docs/diagrams/src/designcore-pipeline.spec.yaml")
needs_backends = pytest.mark.skipif(
    shutil.which("mmdc") is None or shutil.which("dot") is None,
    reason="requires mmdc and dot; run designcore doctor",
)


@needs_backends
def test_renders_and_lints_the_example_diagram(tmp_path):
    (tmp_path / "src").mkdir(parents=True)
    shutil.copy(EXAMPLE, tmp_path / "src" / EXAMPLE.name)

    assert main(["render", "designcore-pipeline", "--root", str(tmp_path), "--format", "mermaid"]) == 0
    # Renders live under out/<format>/ so two formats cannot clobber each other.
    assert (tmp_path / "out" / "mermaid" / "designcore-pipeline.svg").stat().st_size > 0
    assert main(["lint", "designcore-pipeline", "--root", str(tmp_path)]) == 0
    assert main(["check", "--root", str(tmp_path)]) == 0
