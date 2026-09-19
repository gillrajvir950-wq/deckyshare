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
from web_ui import html_page
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

    def new_transfer(self, direction, name, total):
        tid = secrets.token_hex(6)
        now = time.time()
        with self.lock:
            self.transfers[tid] = {
                "id": tid, "direction": direction, "name": name,
                "total": int(total or 0), "done": 0, "started": now,
                "updated": now, "status": "active"
            }
        return tid

    def update_transfer(self, tid, done=None, status=None):
        with self.lock:
            t = self.transfers.get(tid)
            if not t:
                return
            if done is not None:
                t["done"] = int(done)
            if status:
                t["status"] = status
            t["updated"] = time.time()

    def record_received(self, path):
        try:
            p = Path(path).resolve()
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
                if not p.is_file() or p.name.endswith(".deckshare-part"):
                    continue
                try:
                    st = p.stat()
                    disk.append({
                        "name": p.name,
                        "path": str(p.resolve()),
                        "size": st.st_size,
                        "size_human": human_size(st.st_size),
                        "received_at": st.st_mtime,
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
                speed = t["done"] / elapsed
                remain = max(0, t["total"] - t["done"])
                eta = (remain / speed) if speed > 1 else None
                x = dict(t)
                x["speed"] = speed
                x["eta"] = eta
                x["percent"] = (t["done"] * 100 / t["total"]) if t["total"] else 0
                out.append(x)
            return out


STATE = State()
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
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
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
                    chunk = f.read(min(16 * 1024 * 1024, remain))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    sent += len(chunk)
                    remain -= len(chunk)
                    STATE.update_transfer(tid, sent)
            STATE.update_transfer(tid, sent, "complete" if sent == length else "failed")
        except (BrokenPipeError, ConnectionResetError):
            STATE.update_transfer(tid, status="failed")
        except Exception:
            STATE.update_transfer(tid, status="failed")
            raise

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
            "server_self_test": server_self_test(STATE.port),
            "listen": f"0.0.0.0:{STATE.port}",
            "selected": selected_info(),
            "transfers": STATE.snapshot(),
            "receive_dir": str(STATE.receive_dir),
            "received": STATE.received_snapshot(),
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
