from __future__ import annotations

import errno
import html
import mimetypes
import os
import secrets
import time
import urllib.parse
from pathlib import Path


def _settings_dir(decky) -> Path:
    configured = str(os.environ.get("DECKY_PLUGIN_SETTINGS_DIR") or "").strip()
    if configured:
        return Path(configured)
    return Path(decky.DECKY_USER_HOME) / ".config" / "DeckyShare"


def load_or_create_share_key(decky) -> str:
    base = _settings_dir(decky)
    path = base / "iphone-share-key.txt"
    try:
        value = path.read_text(encoding="utf-8").strip()
        if 24 <= len(value) <= 128:
            return value
    except Exception:
        pass
    value = secrets.token_urlsafe(32)
    try:
        base.mkdir(parents=True, exist_ok=True)
        path.write_text(value + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except Exception:
        pass
    return value


def authorized(provided: str, expected: str) -> bool:
    try:
        return bool(provided) and secrets.compare_digest(str(provided), str(expected))
    except Exception:
        return False


def _extension_for_type(content_type: str) -> str:
    ctype = str(content_type or "").split(";", 1)[0].strip().lower()
    known = {
        "text/plain": ".txt",
        "text/uri-list": ".txt",
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/heic": ".heic",
        "image/heif": ".heif",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
    }
    if ctype in known:
        return known[ctype]
    return mimetypes.guess_extension(ctype) or ".bin"


def choose_name(query: dict, headers, content_type: str) -> str:
    raw = ""
    try:
        raw = (query.get("name") or [""])[0]
    except Exception:
        pass
    if not raw:
        raw = str(headers.get("X-DeckyShare-Name") or "").strip()
    if raw:
        safe = Path(urllib.parse.unquote(raw)).name.strip()
        if safe and safe not in (".", ".."):
            return safe[:240]
    stamp = time.strftime("%Y-%m-%d %H-%M-%S")
    ctype = str(content_type or "").lower()
    if ctype.startswith("text/"):
        base = "Shared Text"
    elif ctype.startswith("image/"):
        base = "Shared Photo"
    elif ctype.startswith("video/"):
        base = "Shared Video"
    else:
        base = "Shared File"
    return f"{base} {stamp}{_extension_for_type(content_type)}"


def setup_info(base_url: str, key: str, qr_data_uri_fn=None) -> dict:
    base = str(base_url or "").rstrip("/") + "/"
    quoted = urllib.parse.quote(key, safe="")
    endpoint = f"{base}shortcut/share?key={quoted}&name=Shortcut%20Input"
    setup_url = f"{base}iphone?key={quoted}"
    result = {"enabled": True, "endpoint": endpoint, "setup_url": setup_url, "key_hint": key[-6:] if key else ""}
    return result


def setup_page(base_url: str, key: str) -> str:
    info = setup_info(base_url, key)
    endpoint = html.escape(info["endpoint"])
    return f'''<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>DeckyShare • iPhone Share Sheet</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;background:#0d1726;color:#fff;margin:0;padding:22px}}.wrap{{max-width:680px;margin:auto}}.card{{background:#13253b;border:1px solid #294866;border-radius:18px;padding:18px;margin:14px 0}}h1{{font-size:25px;margin:0 0 5px}}h2{{font-size:18px}}p,li{{line-height:1.45;color:#d6e6f5}}code{{display:block;word-break:break-all;background:#09121e;padding:12px;border-radius:12px;color:#8fd3ff}}button{{width:100%;padding:13px;border:0;border-radius:12px;background:#2d79b7;color:white;font-weight:700;font-size:16px}}.small{{font-size:13px;opacity:.72}}</style></head>
<body><div class="wrap"><h1>📡 DeckyShare Share Sheet</h1><p>One-time setup. After this, Photos / Files / Safari → Share → DeckyShare can send straight to your Steam Deck.</p>
<div class="card"><h2>Shortcut endpoint</h2><code id="ep">{endpoint}</code><br><button onclick="navigator.clipboard.writeText(document.getElementById('ep').innerText).then(()=>this.innerText='✓ Copied')">Copy endpoint</button></div>
<div class="card"><h2>Create the “DeckyShare” shortcut</h2><ol><li>Open <b>Shortcuts</b> and create a shortcut named <b>DeckyShare</b>.</li><li>Enable <b>Show in Share Sheet</b> and allow Files, Images, Media, URLs and Text.</li><li>Add <b>Repeat with Each</b> using Share Sheet input.</li><li>Inside the repeat, get the item name and URL-encode it.</li><li>Add <b>Get Contents of URL</b>, choose <b>POST</b>, paste the endpoint above, replace <code>Shortcut%20Input</code> after <code>name=</code> with the encoded item name, and set request body to the repeated item.</li><li>Add a final notification: <b>Sent to DeckyShare</b>.</li></ol><p class="small">The secret key is already inside the endpoint. Keep this setup URL private on your local network.</p></div>
<div class="card"><b>Tip:</b> Pin DeckyShare near the top of the iPhone Share Sheet for near one-tap sending.</div></div></body></html>'''


def receive_raw(handler, state, query: dict, key: str, unique_destination_path, notify_file_received):
    provided = ""
    try:
        provided = (query.get("key") or [""])[0]
    except Exception:
        pass
    if not provided:
        provided = str(handler.headers.get("X-DeckyShare-Key") or "").strip()
    if not authorized(provided, key):
        return {"error": "Invalid iPhone Share Sheet key"}, 403
    try:
        length = int(handler.headers.get("Content-Length", ""))
    except Exception:
        return {"error": "Content-Length is required"}, 411
    if length < 0:
        return {"error": "Invalid Content-Length"}, 400
    content_type = str(handler.headers.get("Content-Type") or "application/octet-stream")
    name = choose_name(query, handler.headers, content_type)
    target = (state.receive_dir / name).resolve()
    if state.receive_dir.resolve() not in target.parents:
        return {"error": "Bad filename"}, 400
    final_target = unique_destination_path(target)
    part = final_target.with_name(f".{final_target.name}.deckyshare-share-{secrets.token_hex(6)}.part")
    tid = state.new_transfer("upload", final_target.name, length)
    received = 0
    try:
        with open(part, "wb", buffering=0) as f:
            remain = length
            while remain:
                chunk = handler.rfile.read(min(1024 * 1024, remain))
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)
                remain -= len(chunk)
                state.update_transfer(tid, received)
        if received != length:
            try: part.unlink()
            except OSError: pass
            state.update_transfer(tid, received, "failed")
            return {"error": "Upload body ended early", "received": received}, 400
        os.replace(part, final_target)
        state.update_transfer(tid, received, "complete")
        item = state.record_received(final_target)
        notify_file_received(item)
        return {"ok": True, "name": final_target.name, "path": str(final_target), "size": received, "source": "iphone-share-sheet"}, 200
    except OSError as exc:
        state.update_transfer(tid, received, "failed")
        try:
            if part.exists(): part.unlink()
        except OSError: pass
        if exc.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", 122)):
            return {"error": "Not enough storage on Steam Deck"}, 507
        return {"error": f"Could not save shared item: {exc}"}, 500
    except Exception as exc:
        state.update_transfer(tid, received, "failed")
        try:
            if part.exists(): part.unlink()
        except OSError: pass
        return {"error": f"Share failed: {exc}"}, 500


PAIRING_TTL_SECONDS = 10 * 60
PAIRING_WINDOW_SECONDS = 60
PAIRING_MAX_ATTEMPTS = 6


def _pairing_state(state):
    return (
        getattr(state, "shortcut_pairing_code", None),
        float(getattr(state, "shortcut_pairing_expires", 0.0) or 0.0),
    )


def start_pairing(state, base_url: str) -> dict:
    """Create a short-lived one-time code for the public iPhone Shortcut."""
    now = time.time()
    code = f"{secrets.randbelow(1_000_000):06d}"
    with state.lock:
        state.shortcut_pairing_code = code
        state.shortcut_pairing_expires = now + PAIRING_TTL_SECONDS
        state.shortcut_pairing_attempts = {}
    return {
        "ok": True,
        "code": code,
        "address": str(base_url or "").rstrip("/"),
        "expires_at": now + PAIRING_TTL_SECONDS,
        "expires_in": PAIRING_TTL_SECONDS,
        "one_time": True,
    }


def pairing_status(state, base_url: str) -> dict:
    now = time.time()
    with state.lock:
        code, expires = _pairing_state(state)
        if not code or expires <= now:
            state.shortcut_pairing_code = None
            state.shortcut_pairing_expires = 0.0
            return {"ok": True, "active": False, "address": str(base_url or "").rstrip("/")}
        return {
            "ok": True,
            "active": True,
            "code": code,
            "address": str(base_url or "").rstrip("/"),
            "expires_at": expires,
            "expires_in": max(0, int(expires - now)),
            "one_time": True,
        }


def pair_request(state, query: dict, client_ip: str, base_url: str, key: str):
    """Exchange a temporary six-digit code for the authenticated Share Sheet endpoint."""
    now = time.time()
    client = str(client_ip or "unknown")
    provided = str((query.get("code") or [""])[0]).strip()

    with state.lock:
        attempts = getattr(state, "shortcut_pairing_attempts", {})
        recent = [float(t) for t in attempts.get(client, []) if now - float(t) < PAIRING_WINDOW_SECONDS]
        if len(recent) >= PAIRING_MAX_ATTEMPTS:
            attempts[client] = recent
            state.shortcut_pairing_attempts = attempts
            return {"error": "Too many pairing attempts. Wait one minute and try again."}, 429

        expected, expires = _pairing_state(state)
        if not expected or expires <= now:
            state.shortcut_pairing_code = None
            state.shortcut_pairing_expires = 0.0
            return {"error": "Pairing code expired. Start pairing again on Steam Deck."}, 410

        try:
            matches = bool(provided) and secrets.compare_digest(provided, str(expected))
        except Exception:
            matches = False

        if not matches:
            recent.append(now)
            attempts[client] = recent
            state.shortcut_pairing_attempts = attempts
            return {"error": "Invalid pairing code"}, 403

        # One successful exchange consumes the code immediately.
        state.shortcut_pairing_code = None
        state.shortcut_pairing_expires = 0.0
        state.shortcut_pairing_attempts = {}

    info = setup_info(base_url, key)
    return {
        "ok": True,
        "endpoint": info["endpoint"],
        "base_url": str(base_url or "").rstrip("/"),
        "paired_at": now,
    }, 200
