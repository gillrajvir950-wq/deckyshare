import asyncio
import base64
import json
import mimetypes
import os
import secrets
import socket
import subprocess
import ipaddress
import urllib.request
import sys
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie
from decky_http_server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from transfer_integrity import (
    crc32_update,
    crc32_value_hex,
    parse_nonnegative_int,
    validate_upload_window,
)
from web_ui import html_page, pair_page_html
import steam_clips
from share_sheet import (
    authorized as share_sheet_authorized,
    load_or_create_share_key,
    pair_request as share_sheet_pair_request,
    pairing_status as share_sheet_pairing_status,
    receive_raw as receive_share_sheet_raw,
    setup_page as share_sheet_setup_page,
    start_pairing as start_share_sheet_pairing,
)

try:
    import decky  # Current Decky Loader
except ImportError:
    import decky_plugin as decky  # Older Decky Loader compatibility

PLUGIN_DIR = Path(__file__).resolve().parent
PYMOD = PLUGIN_DIR / "py_modules"
if str(PYMOD) not in sys.path:
    sys.path.insert(0, str(PYMOD))

try:
    import qrcode
except Exception:
    qrcode = None

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".m2ts", ".ts"}
ALL_EXTS = VIDEO_EXTS | {".zip", ".7z", ".rar", ".jpg", ".jpeg", ".png", ".gif", ".pdf", ".txt", ".iso"}
PORT_START = 8787
PORT_END = 8797


def human_size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


def unique_destination_path(path):
    """Return a non-existing sibling path without overwriting an existing file."""
    path = Path(path)
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def network_addresses():
    """Return useful IPv4 LAN addresses, preferring Wi-Fi/Ethernet over VPN/virtual links."""
    found = []
    seen = set()

    def add(ip, iface="network"):
        try:
            obj = ipaddress.ip_address(ip)
            if obj.version != 4 or obj.is_loopback or obj.is_link_local or obj.is_multicast or obj.is_unspecified:
                return
        except Exception:
            return
        if ip in seen:
            return
        seen.add(ip)
        lname = iface.lower()
        virtual = any(x in lname for x in ("docker", "podman", "veth", "virbr", "tailscale", "tun", "tap", "wg"))
        private = ipaddress.ip_address(ip).is_private
        score = (0 if virtual else 100) + (50 if private else 0) + (20 if lname.startswith(("wlan", "wlp")) else 0) + (10 if lname.startswith(("eth", "enp", "eno")) else 0)
        found.append({"ip": ip, "interface": iface, "score": score, "private": private, "virtual": virtual})

    try:
        cp = subprocess.run(["ip", "-j", "-4", "addr", "show", "up"], capture_output=True, text=True, timeout=2)
        if cp.returncode == 0:
            for item in json.loads(cp.stdout or "[]"):
                iface = item.get("ifname", "network")
                for ai in item.get("addr_info", []):
                    if ai.get("family") == "inet" and ai.get("local"):
                        add(ai["local"], iface)
    except Exception as e:
        decky.logger.warning(f"DeckyShare address discovery via ip failed: {e}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("1.1.1.1", 80))
        add(sock.getsockname()[0], "default-route")
    except Exception:
        pass
    finally:
        sock.close()

    found.sort(key=lambda x: x["score"], reverse=True)
    return found


def local_ip():
    addrs = network_addresses()
    return addrs[0]["ip"] if addrs else "127.0.0.1"


def server_self_test(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8"))
            return bool(r.status == 200 and data.get("ok"))
    except Exception as e:
        decky.logger.warning(f"DeckyShare self-test failed: {e}")
        return False


def connection_options():
    out = []
    for item in network_addresses():
        ip = item["ip"]
        token = urllib.parse.quote(STATE.token, safe="")
        url = f"http://{ip}:{STATE.port}/?token={token}"
        out.append({
            "ip": ip,
            "interface": item["interface"],
            "url": url,
            "qr_data": qr_data_uri(url),
            "private": item["private"],
            "virtual": item["virtual"],
        })
    return out


# ------------------------------------------------------------ sender devices
# Which kind of device sent each received file ("iPhone", "Mac", ...), taken
# from the uploading request's User-Agent. Kept in the plugin's settings folder
# (never in the user's Downloads) so the Recent list survives a reload.
_REQUEST_LOCAL = threading.local()


def device_from_user_agent(ua):
    ua = str(ua or "")
    low = ua.lower()
    if "iphone" in low or "shortcuts" in low or "backgroundshortcutrunner" in low:
        return "iPhone"
    if "ipad" in low:
        return "iPad"
    if "android" in low or "okhttp" in low or "dalvik" in low:
        return "Android"
    if "cros" in low:
        return "Chromebook"
    if "macintosh" in low or "mac os x" in low:
        return "Mac"
    if "windows" in low:
        return "Windows PC"
    if "steamdeck" in low or "steamos" in low:
        return "Steam Deck"
    if "linux" in low:
        return "Linux PC"
    return None


def current_sender():
    return getattr(_REQUEST_LOCAL, "sender", None)


def with_sender(handler_method):
    def wrapper(self):
        _REQUEST_LOCAL.sender = device_from_user_agent(self.headers.get("User-Agent", "") if getattr(self, "headers", None) else "")
        try:
            return handler_method(self)
        finally:
            _REQUEST_LOCAL.sender = None
    wrapper.__name__ = getattr(handler_method, "__name__", "wrapper")
    return wrapper


class SenderLog:
    LIMIT = 200

    def __init__(self):
        self.lock = threading.Lock()
        self.items = {}
        self.path = None
        settings = getattr(decky, "DECKY_PLUGIN_SETTINGS_DIR", None)
        if settings:
            self.path = Path(settings) / "received_from.json"
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.items = {str(k): str(v) for k, v in data.items() if v}
            except Exception:
                self.items = {}

    def get(self, name):
        with self.lock:
            return self.items.get(name)

    def remember(self, name, device):
        if not device:
            return
        with self.lock:
            self.items.pop(name, None)
            self.items[name] = device
            while len(self.items) > self.LIMIT:
                self.items.pop(next(iter(self.items)))
            if self.path:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = self.path.with_suffix(".tmp")
                    tmp.write_text(json.dumps(self.items), encoding="utf-8")
                    os.replace(tmp, self.path)
                except OSError:
                    pass


SENDERS = SenderLog()


class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.token = secrets.token_urlsafe(12)
        self.selected = None
        self.transfers = {}
        self.received = []
        self.receive_dir = Path(decky.DECKY_USER_HOME) / "Downloads" / "DeckShare"
        self.receive_dir.mkdir(parents=True, exist_ok=True)
        self.port = None
        self.server = None
        self.thread = None
        self.loop = None
        self.share_key = load_or_create_share_key(decky)
        self.shortcut_pairing_code = None
        self.shortcut_pairing_expires = 0.0
        self.shortcut_pairing_attempts = {}
        self.browser_pair_code = None
        self.browser_pair_expires = 0.0
        self.browser_pair_attempts = {}
        self.browser_pair_failures = []
        self.cancel_tids = set()

    def new_transfer(self, direction, name, total, initial_done=0):
        tid = secrets.token_hex(6)
        now = time.time()
        initial_done = max(0, int(initial_done or 0))
        with self.lock:
            self.transfers[tid] = {
                "id": tid, "direction": direction, "name": name,
                "total": int(total or 0), "done": initial_done,
                "base_done": initial_done, "started": now,
                "updated": now, "status": "active",
                "_samples": [(now, initial_done)],
            }
        return tid

    def update_transfer(self, tid, done=None, status=None):
        now = time.time()
        with self.lock:
            t = self.transfers.get(tid)
            if not t:
                return
            if done is not None:
                t["done"] = int(done)
                if t["done"] != t["_samples"][-1][1]:
                    t["last_progress"] = now
                samples = t["_samples"]
                samples.append((now, t["done"]))
                # Keep a short window plus one older sample as the baseline.
                while len(samples) > 2 and now - samples[1][0] > SPEED_WINDOW_SECONDS:
                    samples.pop(0)
            if status:
                t["status"] = status
            t["updated"] = now

    def record_received(self, path):
        try:
            p = Path(path).resolve()
            SENDERS.remember(p.name, current_sender())
            st = p.stat()
            item = {"name": p.name, "path": str(p), "size": st.st_size, "size_human": human_size(st.st_size), "received_at": time.time()}
            with self.lock:
                self.received = [x for x in self.received if x.get("path") != str(p)]
                self.received.insert(0, item)
                self.received = self.received[:50]
            return item
        except Exception:
            return None

    def received_snapshot(self):
        """Return recent received files, including files from before a plugin reload."""
        try:
            disk = []
            for p in self.receive_dir.iterdir():
                # Hidden files include in-progress ".deckyshare-*.part" uploads.
                if not p.is_file() or p.name.startswith(".") or p.name.endswith(".deckshare-part"):
                    continue
                try:
                    st = p.stat()
                    disk.append({
                        "name": p.name,
                        "path": str(p.resolve()),
                        "size": st.st_size,
                        "size_human": human_size(st.st_size),
                        "received_at": st.st_mtime,
                        "from": SENDERS.get(p.name),
                    })
                except OSError:
                    continue
            disk.sort(key=lambda x: x["received_at"], reverse=True)
            with self.lock:
                self.received = disk[:50]
                return list(self.received)
        except Exception:
            with self.lock:
                return list(self.received[:50])

    def snapshot(self):
        now = time.time()
        with self.lock:
            for tid, t in list(self.transfers.items()):
                if t["status"] in ("complete", "failed", "cancelled") and now - t["updated"] > 2.0:
                    self.transfers.pop(tid, None)
            out = []
            for t in self.transfers.values():
                elapsed = max(0.001, now - t["started"])
                avg_speed = max(0, t["done"] - t.get("base_done", 0)) / elapsed
                # Live speed over the last few seconds, measured up to *now*, so
                # a paused transfer drops to 0 instead of slowly decaying like a
                # since-start average does (the old "15 -> 4 MB/s" symptom).
                base_t, base_done = t["_samples"][0]
                for st, sd in t["_samples"]:
                    if now - st <= SPEED_WINDOW_SECONDS:
                        break
                    base_t, base_done = st, sd
                speed = max(0.0, (t["done"] - base_done) / max(0.25, now - base_t))
                last_progress = t.get("last_progress", t["started"])
                stalled = t["status"] == "active" and now - last_progress > STALL_AFTER_SECONDS
                if stalled:
                    speed = 0.0
                remain = max(0, t["total"] - t["done"])
                eta = (remain / speed) if speed > 1 else None
                x = {k: v for k, v in t.items() if not k.startswith("_")}
                x["speed"] = speed
                x["avg_speed"] = avg_speed
                x["stalled"] = stalled
                x["stalled_for"] = round(now - last_progress, 1) if stalled else 0
                x["eta"] = eta
                x["percent"] = (t["done"] * 100 / t["total"]) if t["total"] else 0
                out.append(x)
            return out


SPEED_WINDOW_SECONDS = 3.0
STALL_AFTER_SECONDS = 2.0
STATE = State()
CLIPS = steam_clips.ClipExporter()
_START_SERVER_LOCK = threading.Lock()


def notify_file_received(item):
    """Emit a Decky frontend event from the HTTP server thread."""
    if not item or STATE.loop is None:
        return
    try:
        future = asyncio.run_coroutine_threadsafe(decky.emit("file_received", item), STATE.loop)

        def _finished(f):
            try:
                f.result()
            except Exception as e:
                decky.logger.warning(f"DeckyShare notification event failed: {e}")

        future.add_done_callback(_finished)
    except Exception as e:
        decky.logger.warning(f"DeckyShare could not emit receive notification: {e}")


def allowed_roots():
    home = Path(decky.DECKY_USER_HOME).resolve()
    roots = [
        ("Home", home),
        ("Videos", home / "Videos"),
        ("Downloads", home / "Downloads"),
        ("Desktop", home / "Desktop"),
    ]
    media = Path("/run/media")
    if media.exists():
        for child in media.iterdir():
            if child.is_dir():
                roots.append((f"Drive: {child.name}", child))
    return [(n, p.resolve()) for n, p in roots if p.exists()]


def path_allowed(path):
    try:
        p = Path(path).resolve()
        for _, root in allowed_roots():
            try:
                p.relative_to(root)
                return True
            except ValueError:
                pass
    except Exception:
        pass
    return False


def make_qr_svg(text):
    if qrcode is None:
        return None
    try:
        qr = qrcode.QRCode(border=4, box_size=1)
        qr.add_data(text)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        size = len(matrix)
        rects = []
        for y, row in enumerate(matrix):
            for x, dark in enumerate(row):
                if dark:
                    rects.append(f'<rect x="{x}" y="{y}" width="1" height="1"/>')
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
               f'shape-rendering="crispEdges"><rect width="100%" height="100%" fill="white"/>'
               f'<g fill="black">{"".join(rects)}</g></svg>')
        return svg.encode("utf-8")
    except Exception as e:
        decky.logger.warning(f"DeckyShare QR generation failed: {e}")
        return None


# ------------------------------------------------- PC / Mac browser pairing code
# A computer can't scan the QR code and the tokenised URL is too long to type,
# so the Deck panel shows a short address plus a 6-digit code. Opening the short
# address without a token shows a code page; the right code sets the session
# cookie. Codes expire, are single-use and are rate limited per client and in
# total (too many wrong guesses rotate the code).
BROWSER_PAIR_TTL_SECONDS = 10 * 60
BROWSER_PAIR_WINDOW_SECONDS = 60
BROWSER_PAIR_MAX_PER_CLIENT = 6
BROWSER_PAIR_MAX_TOTAL = 30


def browser_pair_info():
    now = time.time()
    with STATE.lock:
        if not STATE.browser_pair_code or STATE.browser_pair_expires <= now:
            STATE.browser_pair_code = f"{secrets.randbelow(1_000_000):06d}"
            STATE.browser_pair_expires = now + BROWSER_PAIR_TTL_SECONDS
            STATE.browser_pair_attempts = {}
            STATE.browser_pair_failures = []
        return {
            "code": STATE.browser_pair_code,
            "expires_in": max(0, int(STATE.browser_pair_expires - now)),
        }


def browser_pair_check(client, provided):
    """Return (http_status, message). 200 means the code matched and was consumed."""
    now = time.time()
    digits = "".join(ch for ch in str(provided or "") if ch.isdigit())[:12]
    with STATE.lock:
        attempts = STATE.browser_pair_attempts
        recent = [t for t in attempts.get(client, []) if now - t < BROWSER_PAIR_WINDOW_SECONDS]
        if len(recent) >= BROWSER_PAIR_MAX_PER_CLIENT:
            attempts[client] = recent
            return 429, "Too many tries. Wait a minute and try again."
        expected = STATE.browser_pair_code
        if not expected or STATE.browser_pair_expires <= now:
            STATE.browser_pair_code = None
            return 410, "No active code. Open DeckyShare on your Steam Deck to see the code."
        try:
            ok = len(digits) == 6 and secrets.compare_digest(digits, expected)
        except Exception:
            ok = False
        if ok:
            STATE.browser_pair_code = None  # single use; the panel shows a fresh one
            STATE.browser_pair_attempts = {}
            STATE.browser_pair_failures = []
            return 200, "Connected"
        recent.append(now)
        attempts[client] = recent
        failures = [t for t in STATE.browser_pair_failures if now - t < BROWSER_PAIR_WINDOW_SECONDS] + [now]
        STATE.browser_pair_failures = failures
        if len(failures) >= BROWSER_PAIR_MAX_TOTAL:
            STATE.browser_pair_code = None
            return 403, "Too many wrong codes. A new code is now shown on your Deck."
        return 403, "Wrong code. Check the 6 digits on your Steam Deck."


def cancel_transfer_by_id(tid):
    """Stop an active transfer from the Deck panel (upload or download)."""
    with STATE.lock:
        t = STATE.transfers.get(tid)
        if not t or t.get("status") != "active":
            return {"ok": False, "error": "Transfer is no longer active"}
        if t.get("direction") == "download":
            # Stop every active download of this file and stop sharing it, so
            # the browser's automatic Range resume cannot quietly restart it.
            for other_id, other in STATE.transfers.items():
                if other.get("direction") == "download" and other.get("status") == "active" and other.get("name") == t.get("name"):
                    STATE.cancel_tids.add(other_id)
            STATE.selected = None
            return {"ok": True, "cancelled": t.get("name"), "stopped_sharing": True}
        found = [(uid, x) for uid, x in getattr(STATE, "upload_sessions", {}).items() if x.get("tid") == tid]
        sessions = [x for _, x in found]
        # Resumable modes retry with the same upload id; remember it so the
        # retry is refused instead of quietly finishing the file.
        cancelled_ids = getattr(STATE, "deck_cancelled_uploads", None)
        if cancelled_ids is None:
            cancelled_ids = STATE.deck_cancelled_uploads = {}
        now = time.time()
        for uid in list(cancelled_ids):
            if now - cancelled_ids[uid] > 3600:
                del cancelled_ids[uid]
        for uid, _ in found:
            cancelled_ids[uid] = now
    if not sessions:
        STATE.update_transfer(tid, status="cancelled")
        return {"ok": True, "cancelled": t.get("name")}
    for session in sessions:
        session["deck_cancel"] = True
        session["cancel_event"].set()
    STATE.update_transfer(tid, status="cancelled")
    return {"ok": True, "cancelled": t.get("name")}


def plugin_version():
    try:
        data = json.loads((Path(__file__).resolve().parent / "package.json").read_text(encoding="utf-8"))
        return str(data.get("version") or "")
    except Exception:
        return ""


def short_address():
    return f"{local_ip()}:{STATE.port}"


class Handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    server_version = "DeckyShare/1.1-dev"

    def log_message(self, fmt, *args):
        decky.logger.info("DeckyShare HTTP: " + (fmt % args))

    def token_ok(self):
        provided = ""
        try:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            provided = str(query.get("token", [""])[0] or "")
        except Exception:
            provided = ""
        if not provided:
            provided = str(self.headers.get("X-DeckyShare-Token", "") or "")
        if not provided:
            try:
                cookies = SimpleCookie()
                cookies.load(self.headers.get("Cookie", ""))
                morsel = cookies.get("deckyshare_token")
                provided = morsel.value if morsel else ""
            except Exception:
                provided = ""
        try:
            return bool(provided) and secrets.compare_digest(provided, STATE.token)
        except Exception:
            return False

    def loopback_client(self):
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except Exception:
            return False

    def send_json(self, obj, status=200):
        data = json.dumps(obj).encode()
        if status >= 400:
            self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path == "/health":
            return self.send_json({"ok": True})
        if u.path == "/plugin-bootstrap":
            if not self.loopback_client():
                self.send_error(403, "Local Decky access only")
                return
            addr = f"http://{local_ip()}:{STATE.port}/"
            sel = None
            if STATE.selected and STATE.selected.exists():
                st = STATE.selected.stat()
                sel = {"name": STATE.selected.name, "path": str(STATE.selected), "size": st.st_size, "size_human": human_size(st.st_size)}
            status = {"token": STATE.token, "address": addr, "qr": f"http://127.0.0.1:{STATE.port}/qr.svg", "selected": sel, "transfers": STATE.snapshot(), "receive_dir": str(STATE.receive_dir)}
            return self.send_json({"token": STATE.token, "roots": [{"name": n, "path": str(p)} for n, p in allowed_roots()], "status": status})
        if u.path == "/plugin-status":
            if not self.loopback_client():
                self.send_error(403, "Local Decky access only")
                return
            addr = f"http://{local_ip()}:{STATE.port}/"
            sel = None
            if STATE.selected and STATE.selected.exists():
                st = STATE.selected.stat()
                sel = {"name": STATE.selected.name, "path": str(STATE.selected), "size": st.st_size, "size_human": human_size(st.st_size)}
            return self.send_json({"token": STATE.token, "address": addr, "qr": f"http://127.0.0.1:{STATE.port}/qr.svg", "selected": sel, "transfers": STATE.snapshot(), "receive_dir": str(STATE.receive_dir)})
        if u.path == "/share-sheet/setup":
            q = urllib.parse.parse_qs(u.query)
            provided = str((q.get("key") or [""])[0])
            if not share_sheet_authorized(provided, STATE.share_key):
                self.send_error(403, "Invalid DeckyShare Share Sheet key")
                return
            base_url = f"http://{local_ip()}:{STATE.port}"
            data = share_sheet_setup_page(base_url, STATE.share_key).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if u.path == "/" and not self.token_ok():
            data = pair_page_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if not self.token_ok():
            self.send_error(403, "Invalid DeckyShare session")
            return
        if u.path == "/":
            addr = f"http://{local_ip()}:{STATE.port}/"
            data = html_page(addr).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header(
                "Set-Cookie",
                f"deckyshare_token={STATE.token}; Path=/; HttpOnly; SameSite=Strict",
            )
            self.end_headers()
            self.wfile.write(data)
            return
        if u.path == "/qr.svg":
            addr = f"http://{local_ip()}:{STATE.port}/"
            data = make_qr_svg(addr)
            if not data:
                self.send_error(500, "QR unavailable")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if u.path == "/api/status":
            sel = None
            if STATE.selected and STATE.selected.exists():
                st = STATE.selected.stat()
                sel = {"name": STATE.selected.name, "path": str(STATE.selected), "size": st.st_size, "size_human": human_size(st.st_size)}
            return self.send_json({"selected": sel, "transfers": STATE.snapshot(), "receive_dir": str(STATE.receive_dir)})
        if u.path == "/api/roots":
            return self.send_json({"roots": [{"name": n, "path": str(p)} for n, p in allowed_roots()]})
        if u.path == "/api/browse":
            q = urllib.parse.parse_qs(u.query)
            raw = q.get("path", [str(Path(decky.DECKY_USER_HOME))])[0]
            p = Path(raw).resolve()
            if not path_allowed(p) or not p.is_dir():
                return self.send_json({"error": "Path not allowed"}, 403)
            items = []
            try:
                for x in sorted(p.iterdir(), key=lambda z: (not z.is_dir(), z.name.lower())):
                    if x.name.startswith('.'):
                        continue
                    if x.is_dir():
                        items.append({"name": x.name, "path": str(x), "type": "dir"})
                    elif x.suffix.lower() in ALL_EXTS:
                        try:
                            items.append({"name": x.name, "path": str(x), "type": "file", "size": x.stat().st_size, "size_human": human_size(x.stat().st_size)})
                        except OSError:
                            pass
            except OSError as e:
                return self.send_json({"error": str(e)}, 400)
            parent = str(p.parent) if path_allowed(p.parent) else None
            return self.send_json({"path": str(p), "parent": parent, "items": items})
        if u.path == "/download":
            return self.handle_download()
        self.send_error(404)

    def handle_download(self):
        p = STATE.selected
        if not p or not p.exists() or not p.is_file():
            self.send_error(404, "No file selected")
            return
        size = p.stat().st_size
        start = 0
        end = size - 1
        ranged = False
        rh = self.headers.get("Range")
        if rh and rh.startswith("bytes="):
            try:
                a, b = rh[6:].split('-', 1)
                start = int(a) if a else 0
                end = int(b) if b else size - 1
                end = min(end, size - 1)
                ranged = True
            except Exception:
                self.send_error(416)
                return
        if start < 0 or start >= size or end < start:
            self.send_error(416)
            return
        length = end - start + 1
        tid = STATE.new_transfer("download", p.name, length)
        try:
            self.send_response(206 if ranged else 200)
            self.send_header("Content-Type", mimetypes.guess_type(p.name)[0] or "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{p.name.replace(chr(34), "")}"')
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if ranged:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            sent = 0
            with open(p, "rb", buffering=0) as f:
                f.seek(start)
                remain = length
                while remain:
                    if tid in STATE.cancel_tids:
                        # Cancelled from the Deck panel: stop sending and drop the
                        # connection so the browser reports an incomplete download.
                        self.close_connection = True
                        break
                    chunk = f.read(min(16 * 1024 * 1024, remain))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    sent += len(chunk)
                    remain -= len(chunk)
                    STATE.update_transfer(tid, sent)
            if tid in STATE.cancel_tids:
                STATE.cancel_tids.discard(tid)
                STATE.update_transfer(tid, sent, "cancelled")
            else:
                STATE.update_transfer(tid, sent, "complete" if sent == length else "failed")
        except (BrokenPipeError, ConnectionResetError):
            STATE.update_transfer(tid, status="failed")
        except Exception:
            STATE.update_transfer(tid, status="failed")
            raise

    def handle_browser_pair(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > 1024:
            return self.send_json({"error": "Bad request"}, 400)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
            code = str(data.get("code", "")) if isinstance(data, dict) else ""
        except (ValueError, UnicodeDecodeError):
            code = ""
        client = self.client_address[0] if self.client_address else "unknown"
        status, message = browser_pair_check(client, code)
        if status != 200:
            return self.send_json({"ok": False, "error": message}, status)
        body = json.dumps({"ok": True, "redirect": "/"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Set-Cookie", f"deckyshare_token={STATE.token}; Path=/; HttpOnly; SameSite=Strict")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(u.query)
        base_url = f"http://{local_ip()}:{STATE.port}"
        if u.path == "/shortcut/pair":
            result, status = share_sheet_pair_request(
                STATE,
                q,
                self.client_address[0] if self.client_address else "unknown",
                base_url,
                STATE.share_key,
            )
            return self.send_json(result, status)
        if u.path == "/shortcut/share":
            result, status = receive_share_sheet_raw(
                self,
                STATE,
                q,
                STATE.share_key,
                unique_destination_path,
                notify_file_received,
            )
            return self.send_json(result, status)
        if u.path == "/pair":
            return self.handle_browser_pair()
        if not self.token_ok():
            self.send_error(403)
            return
        if u.path == "/api/select":
            n = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(n) or b"{}")
            p = Path(data.get("path", "")).resolve()
            if not path_allowed(p) or not p.is_file():
                return self.send_json({"error": "File not allowed"}, 403)
            STATE.selected = p
            return self.send_json({"ok": True, "name": p.name})
        if u.path == "/api/clear-selection":
            STATE.selected = None
            return self.send_json({"ok": True})
        if u.path == "/api/cancel-upload":
            n = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(n) or b"{}")
            name = Path(data.get("name", "")).name
            if not name:
                return self.send_json({"error": "Missing filename"}, 400)
            target = (STATE.receive_dir / name).resolve()
            if STATE.receive_dir.resolve() not in target.parents:
                return self.send_json({"error": "Bad filename"}, 400)
            part = target.with_name(target.name + ".deckshare-part")
            try:
                if part.exists():
                    part.unlink()
            except OSError as e:
                return self.send_json({"error": str(e)}, 400)
            with STATE.lock:
                for tid, t in STATE.transfers.items():
                    if t["direction"] == "upload" and t["name"] == name and t["status"] == "active":
                        STATE.update_transfer(tid, status="cancelled")
            return self.send_json({"ok": True, "cancelled": name})
        self.send_error(404)

    def do_PUT(self):
        u = urllib.parse.urlsplit(self.path)
        if not self.token_ok():
            self.send_error(403)
            return
        if u.path != "/upload":
            self.send_error(404)
            return
        q = urllib.parse.parse_qs(u.query)
        name = Path(q.get("name", ["upload.bin"])[0]).name
        try:
            offset = parse_nonnegative_int(q.get("offset", ["0"])[0], "offset")
            total = parse_nonnegative_int(q.get("total", ["0"])[0], "total")
            length = parse_nonnegative_int(self.headers.get("Content-Length", "0"), "length")
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)
        target = (STATE.receive_dir / name).resolve()
        if STATE.receive_dir.resolve() not in target.parents:
            return self.send_json({"error": "Bad filename"}, 400)
        part = target.with_name(target.name + ".deckshare-part")
        current = part.stat().st_size if part.exists() else 0
        try:
            validate_upload_window(offset, total, length, current)
        except ValueError as e:
            if str(e) == "Resume offset mismatch":
                return self.send_json({"received": current, "resume": True}, 409)
            return self.send_json({"error": str(e), "received": current}, 400)
        tid = None
        with STATE.lock:
            for k, t in STATE.transfers.items():
                if t["direction"] == "upload" and t["name"] == name and t["status"] == "active":
                    tid = k
                    break
        if not tid:
            tid = STATE.new_transfer("upload", name, total)
        remain = length
        expected_crc = self.headers.get("X-DeckyShare-CRC32", "").strip().lower()
        if expected_crc and (len(expected_crc) != 8 or any(c not in "0123456789abcdef" for c in expected_crc)):
            return self.send_json({"error": "Bad checksum"}, 400)
        crc = 0
        chunk_start = current
        try:
            with open(part, "ab", buffering=0) as f:
                while remain:
                    chunk = self.rfile.read(min(16 * 1024 * 1024, remain))
                    if not chunk:
                        break
                    f.write(chunk)
                    crc = crc32_update(crc, chunk)
                    remain -= len(chunk)
                    current += len(chunk)
                    STATE.update_transfer(tid, current)
                actual_crc = crc32_value_hex(crc)
                if expected_crc and actual_crc != expected_crc:
                    f.truncate(chunk_start)
                    current = chunk_start
                    STATE.update_transfer(tid, current)
                    return self.send_json({"received": current, "checksum_mismatch": True}, 422)
            saved_target = target
            complete = current >= total
            if complete:
                saved_target = unique_destination_path(target)
                if total == 0:
                    if part.exists():
                        part.unlink()
                    saved_target.touch(exist_ok=False)
                else:
                    os.replace(part, saved_target)
                STATE.update_transfer(tid, current, "complete")
                item = STATE.record_received(saved_target)
                notify_file_received(item)
            return self.send_json({
                "received": current,
                "complete": complete,
                "name": saved_target.name if complete else name,
                "verified": bool(expected_crc),
            })
        except Exception:
            STATE.update_transfer(tid, status="failed")
            raise


def start_server():
    with _START_SERVER_LOCK:
        if STATE.server is not None:
            return
        last_error = None
        for port in range(PORT_START, PORT_END + 1):
            try:
                server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
                STATE.port = port
                STATE.server = server
                th = threading.Thread(target=server.serve_forever, name="DeckyShareHTTP", daemon=True)
                th.start()
                STATE.thread = th
                decky.logger.info(f"DeckyShare listening on {port}")
                return
            except OSError as exc:
                last_error = exc
                continue
        raise RuntimeError(f"DeckyShare could not bind a port: {last_error}")


def selected_info():
    if STATE.selected and STATE.selected.exists() and STATE.selected.is_file():
        st = STATE.selected.stat()
        return {"name": STATE.selected.name, "path": str(STATE.selected), "size": st.st_size, "size_human": human_size(st.st_size)}
    return None


def browse_info(path):
    p = Path(path).expanduser().resolve()
    if not path_allowed(p) or not p.is_dir():
        raise ValueError("Folder not allowed")
    items = []
    try:
        entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except PermissionError:
        raise ValueError("Folder cannot be opened")
    for child in entries[:300]:
        try:
            if child.is_dir():
                items.append({"type": "dir", "name": child.name, "path": str(child)})
            elif child.is_file() and child.suffix.lower() in ALL_EXTS:
                st = child.stat()
                items.append({"type": "file", "name": child.name, "path": str(child), "size": st.st_size, "size_human": human_size(st.st_size)})
        except (OSError, PermissionError):
            continue
    parent = None
    pp = p.parent
    if pp != p and path_allowed(pp):
        parent = str(pp)
    return {"path": str(p), "parent": parent, "items": items}


def qr_data_uri(address):
    data = make_qr_svg(address)
    if not data:
        return None
    return "data:image/svg+xml;base64," + base64.b64encode(data).decode("ascii")


def extract_path(value=None, args=(), kwargs=None):
    kwargs = kwargs or {}
    if isinstance(value, dict):
        return value.get("path")
    if isinstance(value, str):
        return value
    if args:
        first = args[0]
        if isinstance(first, dict):
            return first.get("path")
        if isinstance(first, str):
            return first
    return kwargs.get("path")


# ---------------------------------------------------------------- Wi-Fi diagnostics
_WIFI_TOOL_PATHS = "/usr/sbin:/usr/bin:/sbin:/bin"


def _system_env():
    """Environment for system binaries: drop the frozen Decky runtime's library paths."""
    env = {k: v for k, v in os.environ.items() if k not in ("LD_LIBRARY_PATH", "LD_PRELOAD", "PYTHONHOME", "PYTHONPATH")}
    env["PATH"] = _WIFI_TOOL_PATHS + (":" + env["PATH"] if env.get("PATH") else "")
    env["LC_ALL"] = "C"
    return env


def _run_tool(args, timeout=2.0):
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=_system_env())
        return cp.stdout if cp.returncode == 0 else ""
    except Exception:
        return ""


def _wifi_interfaces():
    names = []
    try:
        for d in sorted(Path("/sys/class/net").iterdir()):
            if (d / "wireless").exists() or (d / "phy80211").exists():
                names.append(d.name)
    except OSError:
        pass
    if not names:
        for line in _run_tool(["iw", "dev"]).splitlines():
            line = line.strip()
            if line.startswith("Interface "):
                names.append(line.split(None, 1)[1])
    return names


def _band_for(freq_mhz):
    if not freq_mhz:
        return None
    if freq_mhz < 3000:
        return "2.4 GHz"
    if freq_mhz < 5925:
        return "5 GHz"
    return "6 GHz"


def _parse_bitrate(text):
    """'866.7 MBit/s VHT-MCS 9 80MHz short GI VHT-NSS 2' -> (866.7, 80, 'VHT')."""
    import re
    if not text:
        return None, None, None
    m = re.search(r"([0-9.]+)\s*MBit/s", text)
    rate = float(m.group(1)) if m else None
    w = re.search(r"(\d+)\s*MHz", text)
    width = int(w.group(1)) if w else (20 if rate is not None else None)
    gen = None
    for key, label in (("EHT", "Wi-Fi 7"), ("HE", "Wi-Fi 6"), ("VHT", "Wi-Fi 5"), ("MCS", "Wi-Fi 4")):
        if key + "-" in text or (key == "MCS" and " MCS " in f" {text} "):
            gen = label
            break
    return rate, width, gen


def parse_iw_link(text):
    info = {}
    if not text or "Not connected" in text:
        return {"connected": False}
    info["connected"] = True
    for raw in text.splitlines():
        line = raw.strip()
        key, _, value = line.partition(":")
        value = value.strip()
        if key == "SSID":
            info["ssid"] = value
        elif key == "freq":
            try:
                info["freq_mhz"] = int(float(value.split()[0]))
            except (ValueError, IndexError):
                pass
        elif key == "signal":
            try:
                info["signal_dbm"] = int(float(value.split()[0]))
            except (ValueError, IndexError):
                pass
        elif key in ("tx bitrate", "rx bitrate"):
            rate, width, gen = _parse_bitrate(value)
            prefix = "tx" if key.startswith("tx") else "rx"
            info[prefix + "_mbps"] = rate
            if width:
                info["width_mhz"] = max(width, info.get("width_mhz") or 0)
            if gen and not info.get("standard"):
                info["standard"] = gen
    return info


def parse_nmcli_wifi(text):
    """nmcli -t -f ACTIVE,SSID,FREQ,RATE,SIGNAL dev wifi (':' separated, '\\:' escaped)."""
    for line in (text or "").splitlines():
        parts, cur, i = [], "", 0
        while i < len(line):
            if line[i] == "\\" and i + 1 < len(line):
                cur += line[i + 1]; i += 2; continue
            if line[i] == ":":
                parts.append(cur); cur = ""; i += 1; continue
            cur += line[i]; i += 1
        parts.append(cur)
        if len(parts) >= 5 and parts[0] == "yes":
            info = {"connected": True, "ssid": parts[1]}
            try:
                info["freq_mhz"] = int(parts[2].split()[0])
            except (ValueError, IndexError):
                pass
            try:
                info["tx_mbps"] = float(parts[3].split()[0])
            except (ValueError, IndexError):
                pass
            try:
                info["signal_pct"] = int(parts[4])
            except ValueError:
                pass
            return info
    return {"connected": False}


def wifi_hints(info):
    hints = []
    if not info.get("connected"):
        return ["Deck Wi-Fi is not connected."]
    if info.get("band") == "2.4 GHz":
        hints.append("Connected on 2.4 GHz: expect only ~3-8 MB/s. Join the router's 5 GHz network.")
    if info.get("power_save") is True:
        hints.append("Wi-Fi power saving is ON. Turn off Settings > Developer > Enable Wi-Fi Power Management.")
    sig = info.get("signal_dbm")
    if sig is not None and sig < -70:
        hints.append(f"Weak signal ({sig} dBm). Move closer to the router.")
    rate = info.get("tx_mbps")
    if rate is not None and rate < 200:
        hints.append(f"Low Wi-Fi link rate ({rate:g} Mbit/s): real transfers will be about {rate / 8 / 2:.0f} MB/s or less.")
    width = info.get("width_mhz")
    if info.get("band") == "5 GHz" and width and width < 80:
        hints.append(f"Router channel width is {width} MHz. 80 MHz on 5 GHz roughly doubles speed.")
    if not hints:
        hints.append("Deck Wi-Fi link looks healthy. If transfers are still slow, the router or the other device is the limit.")
    return hints


def wifi_diagnostics():
    ifaces = _wifi_interfaces()
    iface = ifaces[0] if ifaces else None
    info = {"interface": iface, "source": None}
    if iface:
        link = _run_tool(["iw", "dev", iface, "link"])
        if link:
            info.update(parse_iw_link(link))
            info["source"] = "iw"
            ps = _run_tool(["iw", "dev", iface, "get", "power_save"]).lower()
            if "power save:" in ps:
                info["power_save"] = "on" in ps.split("power save:", 1)[1]
    if not info.get("source"):
        nm = _run_tool(["nmcli", "-t", "-f", "ACTIVE,SSID,FREQ,RATE,SIGNAL", "dev", "wifi"])
        if nm:
            info.update(parse_nmcli_wifi(nm))
            info["source"] = "nmcli"
    if not info.get("source"):
        info["connected"] = None
        info["error"] = "Wi-Fi details are unavailable on this system."
        info["hints"] = []
        return info
    info["band"] = _band_for(info.get("freq_mhz"))
    if info.get("freq_mhz"):
        f = info["freq_mhz"]
        info["channel"] = (f - 2407) // 5 if f < 2484 else (14 if f == 2484 else ((f - 5000) // 5 if f < 5925 else (f - 5950) // 5))
    info["hints"] = wifi_hints(info)
    return info


def clips_output_dir():
    return Path(decky.DECKY_USER_HOME) / "Videos" / "Steam Clips"


def _clip_job_snapshot():
    job = CLIPS.snapshot()
    if job and job.get("size") is not None:
        job["size_human"] = human_size(job["size"])
    return job


def _clip_ready(job):
    """Offer a finished clip on the phone page ("Get from Deck")."""
    try:
        p = Path(job["path"])
        if p.is_file() and path_allowed(p):
            STATE.selected = p
    except Exception:
        decky.logger.exception("DeckyShare could not select the exported clip")


def _clip_id(payload, args, kwargs):
    if isinstance(payload, dict):
        return str(payload.get("id") or ""), payload
    if isinstance(payload, str):
        return payload, kwargs
    return str(kwargs.get("id") or ""), kwargs


class Plugin:
    async def bootstrap(self, *args, **kwargs):
        if STATE.server is None:
            await asyncio.wait_for(asyncio.to_thread(start_server), timeout=4.0)
        options = connection_options()
        preferred = options[0] if options else {"url": f"http://127.0.0.1:{STATE.port}/", "qr_data": None}
        return {
            "ok": True,
            "port": STATE.port,
            "token": STATE.token,
            "address": preferred["url"],
            "qr_data": preferred.get("qr_data"),
            "addresses": options,
            "short_address": short_address(),
            "version": plugin_version(),
            "pc_code": browser_pair_info(),
            "server_self_test": server_self_test(STATE.port),
            "listen": f"0.0.0.0:{STATE.port}",
            "selected": selected_info(),
            "transfers": STATE.snapshot(),
            "receive_dir": str(STATE.receive_dir),
            "received": STATE.received_snapshot(),
            "roots": [{"name": n, "path": str(p)} for n, p in allowed_roots()],
        }

    async def status(self, *args, **kwargs):
        if STATE.server is None:
            await asyncio.wait_for(asyncio.to_thread(start_server), timeout=4.0)
        options = connection_options()
        preferred = options[0] if options else {"url": f"http://127.0.0.1:{STATE.port}/"}
        return {
            "ok": True,
            "address": preferred["url"],
            "addresses": options,
            "short_address": short_address(),
            "version": plugin_version(),
            "pc_code": browser_pair_info(),
            "server_self_test": server_self_test(STATE.port),
            "listen": f"0.0.0.0:{STATE.port}",
            "selected": selected_info(),
            "transfers": STATE.snapshot(),
            "receive_dir": str(STATE.receive_dir),
            "received": STATE.received_snapshot(),
            "clip_export": _clip_job_snapshot(),
        }

    async def shortcut_pairing_start(self, *args, **kwargs):
        if STATE.server is None:
            await asyncio.wait_for(asyncio.to_thread(start_server), timeout=4.0)
        return start_share_sheet_pairing(STATE, f"http://{local_ip()}:{STATE.port}")

    async def shortcut_pairing_status(self, *args, **kwargs):
        if STATE.server is None:
            await asyncio.wait_for(asyncio.to_thread(start_server), timeout=4.0)
        return share_sheet_pairing_status(STATE, f"http://{local_ip()}:{STATE.port}")

    async def browse(self, path=None, *args, **kwargs):
        p = extract_path(path, args, kwargs)
        if not p:
            raise ValueError("Missing folder path")
        return browse_info(p)

    async def select_file(self, path=None, *args, **kwargs):
        pth = extract_path(path, args, kwargs)
        if not pth:
            raise ValueError("Missing file path")
        p = Path(pth).expanduser().resolve()
        if not path_allowed(p) or not p.is_file():
            raise ValueError("File not allowed")
        STATE.selected = p
        return {"ok": True, "selected": selected_info()}

    async def clear_selection(self, *args, **kwargs):
        STATE.selected = None
        return {"ok": True}

    async def delete_received(self, path=None, *args, **kwargs):
        pth = extract_path(path, args, kwargs)
        if not pth:
            raise ValueError("Missing file path")
        p = Path(pth).expanduser().resolve()
        root = STATE.receive_dir.resolve()
        try:
            p.relative_to(root)
        except ValueError:
            raise ValueError("Only DeckyShare received files can be deleted")
        if not p.exists() or not p.is_file():
            raise ValueError("File not found")
        p.unlink()
        with STATE.lock:
            STATE.received = [x for x in STATE.received if x.get("path") != str(p)]
        return {"ok": True, "received": STATE.received_snapshot()}

    async def cancel_transfer(self, payload=None, *args, **kwargs):
        tid = payload.get("id") if isinstance(payload, dict) else (payload if isinstance(payload, str) else kwargs.get("id"))
        return cancel_transfer_by_id(str(tid or ""))

    async def list_clips(self, *args, **kwargs):
        try:
            clips = await asyncio.to_thread(steam_clips.list_clips, Path(decky.DECKY_USER_HOME))
        except Exception as exc:
            decky.logger.exception("DeckyShare could not list Steam clips")
            return {"ok": False, "error": str(exc), "clips": []}
        for c in clips:
            c["size_human"] = human_size(c["size"])
        return {"ok": True, "clips": clips, "export": _clip_job_snapshot()}

    async def clip_thumbnail(self, payload=None, *args, **kwargs):
        cid, _ = _clip_id(payload, args, kwargs)
        home = Path(decky.DECKY_USER_HOME)
        if not cid or not steam_clips.is_clip_dir(Path(cid), home):
            return {"ok": False, "error": "Unknown clip"}
        thumb = Path(cid) / "thumbnail.jpg"
        try:
            if thumb.stat().st_size > 512 * 1024:
                return {"ok": False, "error": "Thumbnail too large"}
            data = base64.b64encode(thumb.read_bytes()).decode("ascii")
        except OSError:
            return {"ok": False, "error": "No thumbnail"}
        return {"ok": True, "src": "data:image/jpeg;base64," + data}

    async def export_clip(self, payload=None, *args, **kwargs):
        cid, opts = _clip_id(payload, args, kwargs)
        home = Path(decky.DECKY_USER_HOME)
        if not cid or not steam_clips.is_clip_dir(Path(cid), home):
            return {"ok": False, "error": "Unknown clip"}
        try:
            job = await asyncio.to_thread(CLIPS.start, Path(cid), clips_output_dir(), (opts or {}).get("game"), _clip_ready)
        except steam_clips.ClipError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "export": _clip_job_snapshot() or job}

    async def cancel_clip_export(self, *args, **kwargs):
        CLIPS.stop()
        return {"ok": True}

    async def wifi_info(self, *args, **kwargs):
        try:
            return {"ok": True, "wifi": await asyncio.to_thread(wifi_diagnostics)}
        except Exception as exc:
            decky.logger.exception("DeckyShare Wi-Fi diagnostics failed")
            return {"ok": False, "error": str(exc)}

    async def ping(self, *args, **kwargs):
        if STATE.server is None:
            await asyncio.wait_for(asyncio.to_thread(start_server), timeout=4.0)
        return {"ok": True, "port": STATE.port}

    async def _main(self):
        STATE.loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(asyncio.to_thread(start_server), timeout=4.0)
        except Exception:
            decky.logger.exception("DeckyShare failed to start in _main; frontend bootstrap will retry")

    async def _unload(self):
        if STATE.server:
            STATE.server.shutdown()
            STATE.server.server_close()
            STATE.server = None

    async def _uninstall(self):
        pass
