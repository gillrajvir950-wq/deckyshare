import threading
from pathlib import Path
from types import SimpleNamespace

import rc1_hardening


def test_concurrent_same_name_reservations_are_unique(tmp_path):
    target = tmp_path / "same-name.bin"
    results = []
    errors = []
    barrier = threading.Barrier(12)

    def original_unique(path):
        return Path(path)

    def worker():
        try:
            barrier.wait()
            results.append(rc1_hardening.reserve_unique_destination(original_unique, target))
        except Exception as exc:  # pragma: no cover - diagnostic path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert len(results) == 12
    assert len({str(path) for path in results}) == 12
    assert target in results


def test_install_updates_browser_version_and_is_idempotent(tmp_path):
    state = SimpleNamespace(_rc1_hardening_installed=False)

    def original_unique(path):
        return Path(path)

    core = SimpleNamespace(
        STATE=state,
        unique_destination_path=original_unique,
        html_page=lambda address: f"DeckyShare v1.1-dev at {address}",
    )

    rc1_hardening.install(core)
    first_unique = core.unique_destination_path
    first_html = core.html_page

    assert "v1.1.0-rc1" in core.html_page("http://deck")
    assert "v1.1-dev" not in core.html_page("http://deck")
    assert state._rc1_hardening_installed is True

    rc1_hardening.install(core)
    assert core.unique_destination_path is first_unique
    assert core.html_page is first_html
