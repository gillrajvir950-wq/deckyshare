"""Put received game ROMs straight into the EmuDeck / RetroDECK roms folders.

Only folders that already exist are used (EmuDeck and RetroDECK create one per
system), so DeckyShare never invents a folder name. Files whose system cannot
be told apart safely (.chd, .cue/.bin, .zip, ...) stay in Downloads.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path

# system label -> folder names to try (first existing one wins)
SYSTEMS = {
    "Game Boy": ["gb"],
    "Game Boy Color": ["gbc"],
    "Game Boy Advance": ["gba"],
    "NES": ["nes", "famicom"],
    "SNES": ["snes", "sfc"],
    "Nintendo 64": ["n64"],
    "Nintendo DS": ["nds"],
    "Nintendo 3DS": ["n3ds", "3ds"],
    "Switch": ["switch"],
    "GameCube": ["gc", "gamecube", "ngc"],
    "Wii": ["wii"],
    "Wii U": ["wiiu"],
    "PlayStation": ["psx", "ps1", "playstation"],
    "PlayStation 2": ["ps2"],
    "PSP": ["psp"],
    "PS Vita": ["psvita", "vita"],
    "Genesis / Mega Drive": ["genesis", "megadrive"],
    "Master System": ["mastersystem"],
    "Game Gear": ["gamegear"],
    "Sega 32X": ["sega32x"],
    "PC Engine": ["pcengine", "tg16"],
    "Atari 2600": ["atari2600"],
    "Neo Geo Pocket": ["ngpc", "ngp"],
    "WonderSwan": ["wonderswancolor", "wonderswan"],
}

EXTENSIONS = {
    ".gb": "Game Boy", ".gbc": "Game Boy Color", ".gba": "Game Boy Advance",
    ".nes": "NES", ".fds": "NES", ".sfc": "SNES", ".smc": "SNES",
    ".n64": "Nintendo 64", ".z64": "Nintendo 64", ".v64": "Nintendo 64",
    ".nds": "Nintendo DS", ".3ds": "Nintendo 3DS", ".cci": "Nintendo 3DS", ".cia": "Nintendo 3DS", ".3dsx": "Nintendo 3DS",
    ".nsp": "Switch", ".xci": "Switch", ".nsz": "Switch", ".xcz": "Switch",
    ".gcm": "GameCube", ".gcz": "GameCube", ".wbfs": "Wii", ".wad": "Wii",
    ".wua": "Wii U", ".wux": "Wii U",
    ".pbp": "PSP", ".cso": "PSP", ".vpk": "PS Vita",
    ".md": "Genesis / Mega Drive", ".gen": "Genesis / Mega Drive", ".smd": "Genesis / Mega Drive",
    ".sms": "Master System", ".gg": "Game Gear", ".32x": "Sega 32X", ".pce": "PC Engine",
    ".a26": "Atari 2600", ".ngp": "Neo Geo Pocket", ".ngc": "Neo Geo Pocket",
    ".ws": "WonderSwan", ".wsc": "WonderSwan",
}

GC_MAGIC = bytes.fromhex("C2339F3D")
WII_MAGIC = bytes.fromhex("5D1C9EA3")


def sniff_disc(path: Path):
    """Tell PS1 / PS2 / PSP / GameCube / Wii .iso and .rvz images apart."""
    try:
        with open(path, "rb") as f:
            head = f.read(0x40)
            if head[:4] in (b"RVZ\x01", b"WIA\x01"):
                # WIA/RVZ header 2 starts at 0x48 with disc_type: 1 = GameCube, 2 = Wii.
                f.seek(0x48)
                kind = int.from_bytes(f.read(4), "big")
                return {1: "GameCube", 2: "Wii"}.get(kind)
            if head[0x18:0x1C] == WII_MAGIC:
                return "Wii"
            if head[0x1C:0x20] == GC_MAGIC:
                return "GameCube"
            # ISO9660: look at the first 1 MB for console markers.
            f.seek(0)
            blob = f.read(1024 * 1024)
    except OSError:
        return None
    if b"PSP GAME" in blob or b"UMD_DATA.BIN" in blob or b"PSP_GAME" in blob:
        return "PSP"
    if b"BOOT2" in blob:
        return "PlayStation 2"
    if b"PLAYSTATION" in blob and b"BOOT" in blob:
        return "PlayStation"
    return None


def detect_system(path: Path):
    ext = Path(path).suffix.lower()
    if ext in EXTENSIONS:
        return EXTENSIONS[ext]
    if ext in (".iso", ".rvz", ".wia"):
        return sniff_disc(Path(path))
    return None


_KNOWN = {n for names in SYSTEMS.values() for n in names}


def _expand(raw: str, home: Path):
    v = raw.strip().strip('"').strip("'")
    v = v.replace("$HOME", str(home)).replace("${HOME}", str(home))
    if v.startswith("~"):
        v = str(home) + v[1:]
    return Path(v) if v.startswith("/") else None


def _config_paths(home: Path):
    """roms folders named in EmuDeck / RetroDECK's own settings."""
    out = []
    for f in (home / ".config/EmuDeck/settings.sh", home / "emudeck/settings.sh"):
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        values = {}
        for line in lines:
            line = line.strip()
            for key in ("romsPath", "emulationPath"):
                if line.startswith(key + "="):
                    values[key] = line.split("=", 1)[1].split("#", 1)[0]
        if values.get("romsPath"):
            p = _expand(values["romsPath"], home)
            if p:
                out.append((p, "EmuDeck"))
        if values.get("emulationPath"):
            p = _expand(values["emulationPath"], home)
            if p:
                out.append((p / "roms", "EmuDeck"))
    cfg = home / ".var/app/net.retrodeck.retrodeck/config/retrodeck/retrodeck.cfg"
    try:
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("roms_folder="):
                p = _expand(line.split("=", 1)[1], home)
                if p:
                    out.append((p, "RetroDECK"))
            elif line.startswith("rdhome="):
                p = _expand(line.split("=", 1)[1], home)
                if p:
                    out.append((p / "roms", "RetroDECK"))
    except OSError:
        pass
    return out


def _subdirs(p: Path):
    try:
        return sorted(x for x in p.iterdir() if x.is_dir() and not x.name.startswith("."))
    except OSError:
        return []


def _looks_like_roms(p: Path):
    try:
        names = {x.name.lower() for x in p.iterdir() if x.is_dir()}
    except OSError:
        return False
    return len(names & _KNOWN) >= 4


def _scan(base: Path, depth: int):
    """Find Emulation/roms, retrodeck/roms or any 'roms' folder full of system folders."""
    found = []
    level = [base]
    for _ in range(depth + 1):
        nxt = []
        for d in level:
            for name, app in (("Emulation", "EmuDeck"), ("retrodeck", "RetroDECK")):
                r = d / name / "roms"
                try:
                    if r.is_dir():
                        found.append((r, app))
                except OSError:
                    pass
            if d.name.lower() == "roms" and _looks_like_roms(d):
                found.append((d, "EmuDeck"))
            nxt.extend(_subdirs(d))
        level = nxt[:400]
    return found


_ROOTS_CACHE = {}


def find_roms_roots(user_home: Path, max_age: float = 20.0):
    """[(path, app)] for EmuDeck / RetroDECK roms folders, best first (cached briefly)."""
    key = str(user_home)
    hit = _ROOTS_CACHE.get(key)
    if hit and time.monotonic() - hit[0] < max_age:
        return list(hit[1])
    roots = _find_roms_roots(Path(user_home))
    _ROOTS_CACHE[key] = (time.monotonic(), roots)
    return list(roots)


def _find_roms_roots(user_home: Path):
    home = Path(user_home)
    cands = _config_paths(home)
    cands += [(home / "Emulation" / "roms", "EmuDeck"), (home / "retrodeck" / "roms", "RetroDECK")]
    media = Path("/run/media")
    try:
        if media.is_dir():
            cands += _scan(media, 3)
    except OSError:
        pass
    out, seen = [], set()
    for p, app in cands:
        try:
            if p.is_dir():
                key = p.resolve()
                if key not in seen:
                    seen.add(key)
                    out.append((p, app))
        except OSError:
            pass
    return out


def places_checked(user_home: Path):
    home = Path(user_home)
    places = [str(p) for p, _ in _config_paths(home)]
    places += [str(home / "Emulation/roms"), str(home / "retrodeck/roms"), "/run/media (SD cards and drives)"]
    return places


def target_folder(user_home: Path, system: str):
    for root, app in find_roms_roots(user_home):
        for name in SYSTEMS.get(system, []):
            d = root / name
            if d.is_dir():
                return d, app
    return None, None


def _unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    for n in range(1, 1000):
        cand = dest.with_name(f"{dest.stem} ({n}){dest.suffix}")
        if not cand.exists():
            return cand
    raise OSError("Too many files with this name")


class RomSorter:
    LIMIT = 50

    def __init__(self, user_home: Path, settings_dir: Path | None):
        self.home = Path(user_home)
        self.lock = threading.Lock()
        self.path = Path(settings_dir) / "rom_sort.json" if settings_dir else None
        self.enabled = True
        self.moves = []  # newest first: {name, path, system, app, folder, moved_at, size, from}
        self.active = {}
        self._load()

    def _load(self):
        if not self.path:
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.enabled = bool(data.get("enabled", True))
            self.moves = [m for m in data.get("moves", []) if isinstance(m, dict)][: self.LIMIT]
        except (OSError, ValueError, AttributeError):
            pass

    def _save(self):
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"enabled": self.enabled, "moves": self.moves}), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def set_enabled(self, value: bool):
        with self.lock:
            self.enabled = bool(value)
            self._save()

    def info(self):
        roots = find_roms_roots(self.home)
        return {
            "enabled": self.enabled,
            "found": bool(roots),
            "app": roots[0][1] if roots else None,
            "root": str(roots[0][0]) if roots else None,
            "checked": [] if roots else places_checked(self.home),
            "moving": [dict(v) for v in self.active.values()],
        }

    def forget_move(self, path):
        with self.lock:
            self.moves = [m for m in self.moves if m.get("path") != str(path)]
            self._save()

    def recent_moves(self):
        with self.lock:
            return [dict(m) for m in self.moves if Path(m.get("path", "")).exists()]

    def hint(self, path):
        """For a file still in Downloads: which system it looks like and whether it can be moved."""
        system = detect_system(Path(path))
        if not system:
            return None
        folder, app = target_folder(self.home, system)
        return {"system": system, "can_move": bool(folder), "app": app}

    def maybe_sort(self, path, sender=None, delay=2.0, on_done=None, force=False):
        """If the file is a ROM for a system with an existing folder, move it there (background)."""
        p = Path(path)
        if not self.enabled and not force:
            return None
        system = detect_system(p)
        if not system:
            return None
        folder, app = target_folder(self.home, system)
        if not folder:
            return None
        job = {"name": p.name, "system": system, "app": app, "folder": str(folder), "started": time.time()}
        with self.lock:
            self.active[str(p)] = job
        threading.Thread(target=self._move, args=(p, folder, system, app, sender, delay, on_done), daemon=True).start()
        return dict(job)

    def _move(self, src: Path, folder: Path, system, app, sender, delay, on_done):
        time.sleep(delay)
        result = None
        tmp = None
        try:
            size = src.stat().st_size
            dest = _unique(folder / src.name)
            tmp = dest.with_name(f".deckyshare-moving-{dest.name}")
            try:
                os.replace(src, dest)  # same drive: instant
            except OSError:
                shutil.copyfile(src, tmp)
                if tmp.stat().st_size != size:
                    raise OSError("Copy to the roms folder was incomplete")
                os.replace(tmp, dest)
                src.unlink()
            result = {"name": dest.name, "path": str(dest), "system": system, "app": app,
                      "folder": str(folder), "moved_at": time.time(), "size": size, "from": sender}
            with self.lock:
                self.moves = [m for m in self.moves if m.get("path") != str(dest)]
                self.moves.insert(0, result)
                del self.moves[self.LIMIT:]
                self._save()
        except OSError:
            if tmp is not None:
                try:
                    tmp.unlink()
                except OSError:
                    pass
        finally:
            with self.lock:
                self.active.pop(str(src), None)
        if result and on_done:
            try:
                on_done(result)
            except Exception:
                pass
