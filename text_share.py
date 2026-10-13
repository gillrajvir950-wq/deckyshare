"""Shared clipboard: short texts and links between the phone/PC and the Deck.

Items live in memory and in a small JSON file in the plugin settings folder,
so they survive a restart. Newest first, at most MAX_ITEMS.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

MAX_ITEMS = 30
MAX_CHARS = 20000
_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)


def clean_text(value) -> str:
    text = str(value if value is not None else "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = text.strip()
    if not text:
        raise ValueError("Nothing to send")
    if len(text) > MAX_CHARS:
        raise ValueError(f"Text is too long (max {MAX_CHARS:,} characters)")
    return text


def is_link(text: str) -> bool:
    return bool(_URL.match(text.strip())) and "\n" not in text.strip()


class TextBoard:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.lock = threading.Lock()
        self.items = []
        self.rev = 0
        self._load()

    def _load(self):
        if not self.path:
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data.get("items") if isinstance(data, dict) else None
            if isinstance(items, list):
                self.items = [i for i in items if isinstance(i, dict) and isinstance(i.get("text"), str) and i.get("id")][:MAX_ITEMS]
        except (OSError, ValueError):
            self.items = []

    def _save(self):
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"items": self.items}, ensure_ascii=False), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, self.path)
        except OSError:
            pass

    def add(self, text, source: str) -> dict:
        text = clean_text(text)
        item = {
            "id": secrets.token_hex(6),
            "text": text,
            "from": str(source or "Device")[:40],
            "at": time.time(),
            "link": is_link(text),
        }
        with self.lock:
            # Sending the same text again just moves it to the top.
            self.items = [i for i in self.items if i.get("text") != text]
            self.items.insert(0, item)
            del self.items[MAX_ITEMS:]
            self.rev += 1
            self._save()
        return dict(item)

    def delete(self, item_id: str) -> bool:
        with self.lock:
            before = len(self.items)
            self.items = [i for i in self.items if i.get("id") != item_id]
            changed = len(self.items) != before
            if changed:
                self.rev += 1
                self._save()
            return changed

    def clear(self):
        with self.lock:
            self.items = []
            self.rev += 1
            self._save()

    def snapshot(self):
        with self.lock:
            return [dict(i) for i in self.items]
