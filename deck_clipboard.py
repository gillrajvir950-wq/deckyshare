"""Read the Steam Deck's clipboard from the plugin backend.

The Steam keyboard's Paste key does not reach text boxes inside the Decky
menu, so DeckyShare offers its own Paste button. The Steam UI runs on an X
server provided by gamescope; this asks that server for the CLIPBOARD text
with plain libX11 (no extra packages), using the DISPLAY/XAUTHORITY of the
running Steam client.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import shutil
import subprocess
import time
from pathlib import Path

MAX_BYTES = 1 << 20
SELECTION_NOTIFY = 31


def steam_display_env():
    """DISPLAY and XAUTHORITY of a running Steam process owned by this user."""
    uid = os.getuid()
    best = None
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != uid:
                continue
            comm = (proc / "comm").read_text().strip()
            if comm not in ("steamwebhelper", "steam", "gamescope", "steam-runtime-l"):
                continue
            raw = (proc / "environ").read_bytes()
        except OSError:
            continue
        env = {}
        for item in raw.split(b"\0"):
            if b"=" in item:
                k, _, v = item.partition(b"=")
                if k in (b"DISPLAY", b"XAUTHORITY"):
                    env[k.decode()] = v.decode(errors="replace")
        if env.get("DISPLAY"):
            best = env
            if comm == "steamwebhelper":
                break
    return best or {}


def _displays():
    seen = []
    env = steam_display_env()
    for d in (env.get("DISPLAY"), os.environ.get("DISPLAY"), ":0", ":1"):
        if d and d not in seen:
            seen.append(d)
    return seen, env.get("XAUTHORITY")


def _read_with_tools(display, xauth):
    env = dict(os.environ, DISPLAY=display)
    if xauth:
        env["XAUTHORITY"] = xauth
    for cmd in (["xclip", "-o", "-selection", "clipboard"], ["xsel", "-ob"]):
        if not shutil.which(cmd[0]):
            continue
        try:
            r = subprocess.run(cmd, env=env, capture_output=True, timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0 and r.stdout:
            return r.stdout[:MAX_BYTES].decode("utf-8", "replace")
    return None


class _X11:
    def __init__(self):
        name = ctypes.util.find_library("X11")
        if not name:
            raise OSError("libX11 not found")
        x = ctypes.cdll.LoadLibrary(name)
        vp, ul = ctypes.c_void_p, ctypes.c_ulong
        x.XOpenDisplay.restype, x.XOpenDisplay.argtypes = vp, [ctypes.c_char_p]
        x.XDefaultRootWindow.restype, x.XDefaultRootWindow.argtypes = ul, [vp]
        x.XCreateSimpleWindow.restype = ul
        x.XCreateSimpleWindow.argtypes = [vp, ul, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ul, ul]
        x.XInternAtom.restype, x.XInternAtom.argtypes = ul, [vp, ctypes.c_char_p, ctypes.c_int]
        x.XConvertSelection.argtypes = [vp, ul, ul, ul, ul, ul]
        x.XFlush.argtypes = [vp]
        x.XPending.restype, x.XPending.argtypes = ctypes.c_int, [vp]
        x.XNextEvent.argtypes = [vp, vp]
        x.XGetWindowProperty.restype = ctypes.c_int
        x.XGetWindowProperty.argtypes = [vp, ul, ul, ctypes.c_long, ctypes.c_long, ctypes.c_int, ul,
                                         ctypes.POINTER(ul), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ul),
                                         ctypes.POINTER(ul), ctypes.POINTER(ctypes.c_void_p)]
        x.XFree.argtypes = [vp]
        x.XDestroyWindow.argtypes = [vp, ul]
        x.XCloseDisplay.argtypes = [vp]
        self.x = x

    def read(self, display, timeout=1.5):
        x = self.x
        dpy = x.XOpenDisplay(display.encode())
        if not dpy:
            return None
        win = 0
        try:
            root = x.XDefaultRootWindow(dpy)
            win = x.XCreateSimpleWindow(dpy, root, 0, 0, 1, 1, 0, 0, 0)
            clipboard = x.XInternAtom(dpy, b"CLIPBOARD", 0)
            utf8 = x.XInternAtom(dpy, b"UTF8_STRING", 0)
            prop = x.XInternAtom(dpy, b"DECKYSHARE_PASTE", 0)
            x.XConvertSelection(dpy, clipboard, utf8, prop, win, 0)
            x.XFlush(dpy)
            event = (ctypes.c_long * 24)()  # sizeof(XEvent) == 192 on 64-bit
            deadline = time.monotonic() + timeout
            while True:
                if x.XPending(dpy):
                    x.XNextEvent(dpy, ctypes.byref(event))
                    if ctypes.cast(event, ctypes.POINTER(ctypes.c_int))[0] == SELECTION_NOTIFY:
                        break
                elif time.monotonic() > deadline:
                    return None
                else:
                    time.sleep(0.01)
            # XSelectionEvent.property sits at byte 56 (8th unsigned long).
            if ctypes.cast(event, ctypes.POINTER(ctypes.c_ulong))[7] == 0:
                return None  # nothing copied, or the owner refused
            actual_type, actual_format = ctypes.c_ulong(), ctypes.c_int()
            nitems, after, data = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_void_p()
            status = x.XGetWindowProperty(dpy, win, prop, 0, MAX_BYTES // 4, 1, 0,
                                          ctypes.byref(actual_type), ctypes.byref(actual_format),
                                          ctypes.byref(nitems), ctypes.byref(after), ctypes.byref(data))
            if status != 0 or not data.value:
                return None
            try:
                if actual_format.value != 8:
                    return None
                return ctypes.string_at(data.value, nitems.value).decode("utf-8", "replace")
            finally:
                x.XFree(data)
        finally:
            if win:
                x.XDestroyWindow(dpy, win)
            x.XCloseDisplay(dpy)


def read_clipboard():
    """Return (text, how) or (None, reason)."""
    displays, xauth = _displays()
    if xauth and not os.environ.get("XAUTHORITY"):
        os.environ["XAUTHORITY"] = xauth  # libX11 reads it from the environment
    try:
        lib = _X11()
    except OSError:
        lib = None
    for d in displays:
        if lib is not None:
            try:
                text = lib.read(d)
            except Exception:  # noqa: BLE001 - try the next way
                text = None
            if text:
                return text, f"x11 {d}"
        text = _read_with_tools(d, xauth)
        if text:
            return text, f"tool {d}"
    return None, "The Deck clipboard is empty or could not be read"
