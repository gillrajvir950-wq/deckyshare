import threading
import time
from pathlib import Path


_reservation_lock = threading.Lock()
# path -> monotonic time it was handed out. A reservation only has to cover the
# moment between choosing a name and the file landing on disk (os.replace right
# after); after that the file's own existence protects the name. Reservations
# used to be kept forever, so re-sending a file the user had deleted produced
# "name (1).ext" until Decky restarted.
_RESERVATION_SECONDS = 5.0
_reserved_destinations = {}


def _prune_reservations(now):
    for key, at in list(_reserved_destinations.items()):
        # Landed on disk: the file itself now guards the name. Stale: the
        # finalizer that took it failed or was cancelled.
        if now - at > _RESERVATION_SECONDS or Path(key).exists():
            del _reserved_destinations[key]


def reserve_unique_destination(original_unique, path):
    """Reserve a unique final filename across concurrent upload finalizers."""
    base = Path(path)
    with _reservation_lock:
        now = time.monotonic()
        _prune_reservations(now)
        candidate = Path(original_unique(base))
        if str(candidate) not in _reserved_destinations:
            _reserved_destinations[str(candidate)] = now
            return candidate

        stem = base.stem
        suffix = base.suffix
        counter = 1
        while True:
            candidate = base.with_name(f"{stem} ({counter}){suffix}")
            key = str(candidate)
            if not candidate.exists() and key not in _reserved_destinations:
                _reserved_destinations[key] = now
                return candidate
            counter += 1


def install(core):
    if getattr(core.STATE, "_rc1_hardening_installed", False):
        return

    original_unique = core.unique_destination_path
    original_html = core.html_page

    def unique_destination_path(path):
        return reserve_unique_destination(original_unique, path)

    def html_page(address):
        page = original_html(address)
        return page.replace("v1.1-dev", "v1.1.0-rc1")

    core.unique_destination_path = unique_destination_path
    core.html_page = html_page
    core.STATE._rc1_hardening_installed = True
