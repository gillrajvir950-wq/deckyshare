import threading
from pathlib import Path


_reservation_lock = threading.Lock()
_reserved_destinations = set()


def reserve_unique_destination(original_unique, path):
    """Reserve a unique final filename across concurrent upload finalizers."""
    base = Path(path)
    with _reservation_lock:
        candidate = Path(original_unique(base))
        if str(candidate) not in _reserved_destinations:
            _reserved_destinations.add(str(candidate))
            return candidate

        stem = base.stem
        suffix = base.suffix
        counter = 1
        while True:
            candidate = base.with_name(f"{stem} ({counter}){suffix}")
            key = str(candidate)
            if not candidate.exists() and key not in _reserved_destinations:
                _reserved_destinations.add(key)
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
        return page.replace("v1.1-dev", "v1.1.0-rc2")

    core.unique_destination_path = unique_destination_path
    core.html_page = html_page
    core.STATE._rc1_hardening_installed = True
