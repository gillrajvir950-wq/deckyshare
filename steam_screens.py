"""Steam screenshots on the Deck.

Steam keeps screenshots per game in
    <Steam>/userdata/<id>/760/remote/<appid>/screenshots/<YYYYMMDDHHMMSS>_<n>.jpg
with small previews in .../screenshots/thumbnails/<same name>.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
NAME_RE = re.compile(r"^(\d{14})(?:_\d+)?\.[A-Za-z]+$")
MAX_THUMB_BYTES = 400 * 1024


def _steam_dirs(user_home: Path):
    home = Path(user_home)
    seen, out = set(), []
    for steam in (home / ".local/share/Steam", home / ".steam/steam", home / ".steam/root"):
        userdata = steam / "userdata"
        if not userdata.is_dir():
            continue
        try:
            real = userdata.resolve()
        except OSError:
            continue
        if real in seen:
            continue
        seen.add(real)
        out.append(userdata)
    return out


def screenshot_roots(user_home: Path):
    roots = []
    for userdata in _steam_dirs(user_home):
        try:
            for uid in userdata.iterdir():
                remote = uid / "760" / "remote"
                if remote.is_dir():
                    roots.append(remote)
        except OSError:
            pass
    return roots


def _taken(path: Path):
    m = NAME_RE.match(path.name)
    if m:
        try:
            return time.mktime(time.strptime(m.group(1), "%Y%m%d%H%M%S"))
        except ValueError:
            pass
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def list_screenshots(user_home: Path, limit=300):
    items = []
    for remote in screenshot_roots(user_home):
        try:
            games = list(remote.iterdir())
        except OSError:
            continue
        for game in games:
            shots = game / "screenshots"
            if not shots.is_dir():
                continue
            try:
                files = list(shots.iterdir())
            except OSError:
                continue
            for f in files:
                if f.suffix.lower() not in IMAGE_EXTS or not f.is_file():
                    continue
                try:
                    size = f.stat().st_size
                except OSError:
                    continue
                thumb = shots / "thumbnails" / f.name
                items.append({
                    "id": str(f),
                    "name": f.name,
                    "appid": game.name,
                    "taken": _taken(f),
                    "size": size,
                    "has_thumbnail": thumb.is_file(),
                })
    items.sort(key=lambda x: x["taken"], reverse=True)
    return items[:limit]


def is_screenshot(path, user_home: Path) -> bool:
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    if p.suffix.lower() not in IMAGE_EXTS or not p.is_file() or p.parent.name != "screenshots":
        return False
    for remote in screenshot_roots(user_home):
        try:
            p.relative_to(remote.resolve())
            return True
        except (ValueError, OSError):
            pass
    return False


def thumbnail_path(path: Path) -> Path:
    """Steam's small preview if present, otherwise the picture itself."""
    p = Path(path)
    thumb = p.parent / "thumbnails" / p.name
    return thumb if thumb.is_file() else p
