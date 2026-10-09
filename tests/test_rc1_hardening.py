import threading
import time
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


def test_reservation_expires_so_deleted_names_can_be_reused(tmp_path):
    target = tmp_path / "again.bin"

    def original_unique(path):
        return Path(path)

    first = rc1_hardening.reserve_unique_destination(original_unique, target)
    assert first == target
    # While reserved (file not yet on disk) a second finalizer gets another name.
    second = rc1_hardening.reserve_unique_destination(original_unique, target)
    assert second != target
    # Once the reservation window has passed and the file is gone (the user
    # deleted it), the original name is free again.
    with rc1_hardening._reservation_lock:
        for key in list(rc1_hardening._reserved_destinations):
            rc1_hardening._reserved_destinations[key] = time.monotonic() - rc1_hardening._RESERVATION_SECONDS - 1
    assert rc1_hardening.reserve_unique_destination(original_unique, target) == target


def test_landed_file_releases_its_reservation(tmp_path):
    target = tmp_path / "video.mp4"

    def original_unique(path):
        path = Path(path)
        return path if not path.exists() else path.with_name("video (9).mp4")

    assert rc1_hardening.reserve_unique_destination(original_unique, target) == target
    target.write_bytes(b"x")  # upload finalised: file is on disk
    other = tmp_path / "other.bin"
    rc1_hardening.reserve_unique_destination(original_unique, other)  # any later finalizer prunes
    assert str(target) not in rc1_hardening._reserved_destinations
    target.unlink()  # user deletes it on the Deck
    assert rc1_hardening.reserve_unique_destination(original_unique, target) == target
