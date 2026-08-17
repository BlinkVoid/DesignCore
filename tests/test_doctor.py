from designcore.doctor import BACKENDS, check_backends


def test_reports_available_backend_with_its_path():
    statuses = check_backends(which=lambda cmd: f"/usr/bin/{cmd}", is_dir=lambda p: True)
    assert all(s.available for s in statuses)
    assert len(statuses) == len(BACKENDS)


def test_reports_missing_backend_with_install_hint():
    statuses = check_backends(which=lambda cmd: None, is_dir=lambda p: False)
    missing = [s for s in statuses if not s.available]
    assert len(missing) == len(BACKENDS)
    for status in missing:
        assert status.path is None
        assert status.backend.install_hint


def test_covers_the_three_render_backends():
    names = {b.name for b in BACKENDS}
    assert {"mermaid", "graphviz", "drawio"} <= names


def test_doctor_covers_every_backend_the_renderers_require():
    """doctor is the pre-flight gate, so a backend a renderer hard-requires
    must appear here -- otherwise doctor reports all-ok on a machine where
    `designcore render x --format excalidraw` cannot run."""
    names = {backend.name for backend in BACKENDS}
    assert {"chrome", "excalidraw-deps"} <= names


def test_excalidraw_deps_check_looks_at_the_shipped_helper():
    from designcore.render.excalidraw import HELPER_DIR

    backend = next(b for b in BACKENDS if b.name == "excalidraw-deps")
    assert str(HELPER_DIR) in backend.install_hint
