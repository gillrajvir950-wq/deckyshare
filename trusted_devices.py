"""Remembered phones and computers.

The session token in the QR code changes whenever DeckyShare restarts, which
used to mean scanning again after every reboot. A device that connected once
(QR code or 6-digit code) now also gets a long-lived cookie; the Deck keeps
only a hash of it, and the device can be forgotten from the panel.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

COOKIE = "deckyshare_device"
MAX_AGE = 400 * 24 * 3600
LIMIT = 30


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class DeviceStore:
    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self.lock = threading.Lock()
        self.devices = []  # {id, hash, name, created, last_seen}
        self._load()

    def _load(self):
        if not self.path:
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.devices = [d for d in data.get("devices", []) if isinstance(d, dict) and d.get("id") and d.get("hash")]
        except (OSError, ValueError, AttributeError):
            self.devices = []

    def _save(self):
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"devices": self.devices}), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, self.path)
        except OSError:
            pass

    def create(self, name: str | None) -> str:
        """Remember a new device; returns the cookie value to give it."""
        did, secret = secrets.token_hex(6), secrets.token_urlsafe(24)
        now = time.time()
        with self.lock:
            self.devices.insert(0, {"id": did, "hash": _hash(secret), "name": (name or "Device")[:40], "created": now, "last_seen": now})
            # Forget the least recently used devices beyond the limit.
            self.devices.sort(key=lambda d: d.get("last_seen", 0), reverse=True)
            del self.devices[LIMIT:]
            self._save()
        return f"{did}.{secret}"

    def verify(self, value: str):
        if not value or "." not in value:
            return None
        did, _, secret = value.partition(".")
        digest = _hash(secret)
        with self.lock:
            for d in self.devices:
                if d["id"] == did and secrets.compare_digest(d["hash"], digest):
                    now = time.time()
                    if now - d.get("last_seen", 0) > 60:
                        d["last_seen"] = now
                        self._save()
                    return dict(d)
        return None

    def list(self):
        with self.lock:
            return [{k: d[k] for k in ("id", "name", "created", "last_seen") if k in d} for d in self.devices]

    def forget(self, did: str) -> bool:
        with self.lock:
            before = len(self.devices)
            self.devices = [d for d in self.devices if d["id"] != did]
            changed = len(self.devices) != before
            if changed:
                self._save()
            return changed

    def forget_all(self):
        with self.lock:
            self.devices = []
            self._save()


def cookie_header(value: str) -> str:
    return f"{COOKIE}={value}; Path=/; Max-Age={MAX_AGE}; HttpOnly; SameSite=Lax"
