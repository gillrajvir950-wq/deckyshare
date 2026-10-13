"""Type text into the focused text box on the Deck through a virtual keyboard.

Gaming Mode has no reliable paste: the on-screen keyboard has no paste key and
many games ignore the clipboard. DeckyShare instead creates a short-lived
virtual USB keyboard (Linux uinput) and types the text key by key, like a real
keyboard plugged into the Deck would. US layout; characters a US keyboard
cannot type are skipped and reported.
"""
from __future__ import annotations

import fcntl
import os
import struct
import threading
import time

# linux/input-event-codes.h
EV_SYN, EV_KEY, SYN_REPORT = 0x00, 0x01, 0
KEY_LEFTSHIFT, KEY_ENTER, KEY_TAB, KEY_SPACE = 42, 28, 15, 57

_PLAIN = {
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    "-": 12, "=": 13, "q": 16, "w": 17, "e": 18, "r": 19, "t": 20, "y": 21, "u": 22, "i": 23,
    "o": 24, "p": 25, "[": 26, "]": 27, "a": 30, "s": 31, "d": 32, "f": 33, "g": 34, "h": 35,
    "j": 36, "k": 37, "l": 38, ";": 39, "'": 40, "`": 41, "\\": 43, "z": 44, "x": 45, "c": 46,
    "v": 47, "b": 48, "n": 49, "m": 50, ",": 51, ".": 52, "/": 53, " ": KEY_SPACE, "\t": KEY_TAB,
}
_SHIFTED = {
    "!": 2, "@": 3, "#": 4, "$": 5, "%": 6, "^": 7, "&": 8, "*": 9, "(": 10, ")": 11,
    "_": 12, "+": 13, "{": 26, "}": 27, ":": 39, '"': 40, "~": 41, "|": 43, "<": 51, ">": 52, "?": 53,
}
# Look-alike characters phones like to insert, typed as their plain version.
_REPLACE = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
            " ": " ", "…": "...", "•": "*"}

MAX_TYPE_CHARS = 2000

# linux/uinput.h ioctls (x86_64)
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
BUS_VIRTUAL = 0x06


class KeyboardError(Exception):
    pass


def plan_keys(text: str, enter_for_newlines: bool = False):
    """Turn text into [(keycode, shift)], plus the number of skipped characters."""
    keys, skipped = [], 0
    for ch in text.replace("\r\n", "\n").replace("\r", "\n"):
        ch = _REPLACE.get(ch, ch)
        for c in ch:
            if c == "\n":
                keys.append((KEY_ENTER, False) if enter_for_newlines else (KEY_SPACE, False))
            elif c in _PLAIN:
                keys.append((_PLAIN[c], False))
            elif c.lower() in _PLAIN and c.isalpha() and c.isascii():
                keys.append((_PLAIN[c.lower()], True))
            elif c in _SHIFTED:
                keys.append((_SHIFTED[c], True))
            else:
                skipped += 1
    return keys, skipped


def _event(type_, code, value):
    now = time.time()
    sec = int(now)
    return struct.pack("llHHi", sec, int((now - sec) * 1_000_000), type_, code, value)


class VirtualKeyboard:
    def __init__(self, path="/dev/uinput"):
        try:
            self.fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        except PermissionError as exc:
            raise KeyboardError("No permission to create a keyboard on this Deck") from exc
        except FileNotFoundError as exc:
            raise KeyboardError("Virtual keyboard support (uinput) is not available") from exc
        try:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_SYN)
            for code in set(_PLAIN.values()) | set(_SHIFTED.values()) | {KEY_LEFTSHIFT, KEY_ENTER}:
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            name = b"DeckyShare keyboard"
            # struct uinput_user_dev: name[80], input_id (4 x u16), ff_effects_max, abs arrays
            dev = struct.pack("80sHHHHi", name, BUS_VIRTUAL, 0x1209, 0xD5C1, 1, 0) + b"\x00" * (4 * 64 * 4)
            os.write(self.fd, dev)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except OSError as exc:
            os.close(self.fd)
            raise KeyboardError(f"Could not create the virtual keyboard: {exc}") from exc

    def _key(self, code, value):
        os.write(self.fd, _event(EV_KEY, code, value))
        os.write(self.fd, _event(EV_SYN, SYN_REPORT, 0))

    def tap(self, code, shift=False, gap=0.008):
        if shift:
            self._key(KEY_LEFTSHIFT, 1)
        self._key(code, 1)
        time.sleep(gap)
        self._key(code, 0)
        if shift:
            self._key(KEY_LEFTSHIFT, 0)
        time.sleep(gap)

    def close(self):
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        os.close(self.fd)


class Typist:
    """Runs one typing job at a time in the background."""

    def __init__(self, keyboard_factory=VirtualKeyboard):
        self.factory = keyboard_factory
        self.lock = threading.Lock()
        self.job = None
        self.cancel = threading.Event()

    def snapshot(self):
        with self.lock:
            return dict(self.job) if self.job else None

    def start(self, text: str, delay: float = 1.5, enter_for_newlines: bool = False):
        text = str(text or "")
        if not text.strip():
            raise KeyboardError("Nothing to type")
        if len(text) > MAX_TYPE_CHARS:
            raise KeyboardError(f"Too long to type (max {MAX_TYPE_CHARS} characters)")
        keys, skipped = plan_keys(text, enter_for_newlines)
        if not keys:
            raise KeyboardError("None of these characters can be typed with a keyboard")
        with self.lock:
            if self.job and self.job.get("state") in ("waiting", "typing"):
                raise KeyboardError("Already typing")
            self.cancel.clear()
            self.job = {"state": "waiting", "total": len(keys), "done": 0, "skipped": skipped, "error": None}
            job = dict(self.job)
        threading.Thread(target=self._run, args=(keys, max(0.0, min(float(delay), 10.0))), daemon=True).start()
        return job

    def _set(self, **kw):
        with self.lock:
            if self.job:
                self.job.update(kw)

    def _run(self, keys, delay):
        kb = None
        try:
            kb = self.factory()
            # Give Steam time to notice the new keyboard and the menu time to close.
            end = time.monotonic() + max(delay, 0.6)
            while time.monotonic() < end:
                if self.cancel.is_set():
                    raise KeyboardError("Cancelled")
                time.sleep(0.05)
            self._set(state="typing")
            for i, (code, shift) in enumerate(keys, start=1):
                if self.cancel.is_set():
                    raise KeyboardError("Cancelled")
                kb.tap(code, shift)
                if i % 10 == 0 or i == len(keys):
                    self._set(done=i)
            time.sleep(0.05)
            kb.close()
            kb = None
            self._set(state="done", done=len(keys))
        except KeyboardError as exc:
            self._set(state="error", error=str(exc))
        except Exception as exc:  # noqa: BLE001 - shown in the panel
            self._set(state="error", error=f"Typing failed: {exc}")
        finally:
            if kb is not None:
                time.sleep(0.05)
                kb.close()

    def stop(self):
        self.cancel.set()
