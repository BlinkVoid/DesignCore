from designcore.doctor import BACKENDS, check_backends


def test_reports_available_backend_with_its_path():
    statuses = check_backends(which=lambda cmd: f"/usr/bin/{cmd}")
    assert all(s.available for s in statuses)
    assert len(statuses) == len(BACKENDS)


def test_reports_missing_backend_with_install_hint():
    statuses = check_backends(which=lambda cmd: None)
    missing = [s for s in statuses if not s.available]
    assert len(missing) == len(BACKENDS)
    for status in missing:
        assert status.path is None
        assert status.backend.install_hint


def test_covers_the_three_render_backends():
    names = {b.name for b in BACKENDS}
    assert {"mermaid", "graphviz", "drawio"} <= names
