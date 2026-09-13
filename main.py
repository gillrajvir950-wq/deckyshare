import asyncio
import base64
import html
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from transfer_integrity import crc32_update, crc32_value_hex

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
        decky.logger.warning(f"DeckShare address discovery via ip failed: {e}")

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
            add(info[4][0], "hostname")
    except Exception:
        pass

    # Route-selected address as a final fallback.
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
        decky.logger.warning(f"DeckShare self-test failed: {e}")
        return False


def connection_options():
    out = []
    for item in network_addresses():
        ip = item["ip"]
        url = f"http://{ip}:{STATE.port}/"
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
            # Auto-remove completed/failed entries after ~2 seconds.
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

def notify_file_received(item):
    """Emit a Decky frontend event from the HTTP server thread."""
    if not item or STATE.loop is None:
        return
    try:
        future = asyncio.run_coroutine_threadsafe(
            decky.emit("file_received", item),
            STATE.loop
        )
        def _finished(f):
            try:
                f.result()
            except Exception as e:
                decky.logger.warning(f"DeckShare notification event failed: {e}")
        future.add_done_callback(_finished)
    except Exception as e:
        decky.logger.warning(f"DeckShare could not emit receive notification: {e}")


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
               f'<g fill="black'>{"".join(rects)}</g></svg>')
        return svg.encode("utf-8")
    except Exception as e:
        decky.logger.warning(f"DeckShare QR generation failed: {e}")
        return None

def html_page(address):
    esc = html.escape(address)
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DeckyShare</title><style>
*{{box-sizing:border-box}} body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:linear-gradient(180deg,#081525,#050d18);color:#fff;margin:0;padding:16px}} .wrap{{max-width:760px;margin:auto}} .card{{background:linear-gradient(180deg,rgba(24,48,80,.94),rgba(13,29,50,.94));border:1px solid rgba(92,163,255,.28);border-radius:16px;padding:16px;margin:14px 0;box-shadow:0 10px 28px rgba(0,0,0,.22)}} h1{{margin:4px 0 4px;font-size:27px}} h2{{margin:0 0 8px;font-size:19px}} button,.btn,input[type=file]{{font-size:16px}} button,.btn{{display:inline-block;background:linear-gradient(180deg,rgba(49,97,157,.9),rgba(27,57,96,.9));color:#fff;border:1px solid rgba(110,180,255,.32);border-radius:12px;padding:12px 14px;text-decoration:none;font-weight:700;cursor:pointer}} button:disabled{{opacity:.55;cursor:not-allowed}} input[type=file]{{width:100%;padding:12px;border-radius:12px;border:1px dashed rgba(120,185,255,.35);background:rgba(26,59,99,.45);color:#fff}} .muted{{color:#9db3ca}} .bar{{height:10px;background:rgba(255,255,255,.12);border-radius:999px;overflow:hidden}} .fill{{height:100%;background:#66c0f4;width:0}} .row{{margin:10px 0}} .controls{{display:flex;gap:8px;flex-wrap:wrap}} .queue-item{{padding:8px 0;border-bottom:1px solid rgba(255,255,255,.08)}} .queue-item:last-child{{border-bottom:0}} code{{word-break:break-all}}
</style></head><body><div class="wrap"><h1>DeckyShare <span style="font-size:12px;opacity:.65">v1.0.5-dev</span></h1><div class="muted">Share files with your Steam Deck. Simple. Wireless. Fast.</div>
<div class="card"><h2>Receive from Deck</h2><div id="selected">Loading…</div><div class="row"><a id="download" class="btn" style="display:none">Download selected file</a></div></div>
<div class="card"><h2>Send to Deck</h2><p class="muted">Select one or more files. They will be queued and sent to Downloads/DeckShare.</p><input id="file" type="file" multiple><div class="row controls"><button id="upload">Send selected files</button><button id="pause" disabled>Pause</button><button id="cancel" disabled>Cancel</button></div><div id="uptext" class="muted"></div><div class="bar"><div id="upbar" class="fill"></div></div><div id="queue" class="muted row"></div></div>
<div class="card"><h2>Live transfers</h2><div id="transfers" class="muted">No active transfer</div></div>
<div class="card muted">Connected to <code>{esc}</code></div><div class="card"><h2>☕ Support DeckyShare</h2><p class="muted">DeckyShare is free and open source. If it helps you, you can support future development.</p><a class="btn" href="https://buymeacoffee.com/Gillrv" target="_blank" rel="noopener">Buy me a coffee</a></div></div>
<script>
async function api(path,opt){{let r=await fetch(path,opt); if(!r.ok) throw new Error(await r.text()); return r;}}
async function refresh(){{try{{let s=await (await api('/api/status')).json(); let el=document.getElementById('selected'); let a=document.getElementById('download'); if(s.selected){{el.textContent=s.selected.name+' — '+s.selected.size_human;a.style.display='inline-block';a.href='/download'}}else{{el.textContent='Choose a file in the Decky panel first.';a.style.display='none'}} let box=document.getElementById('transfers'); if(!s.transfers.length) box.innerHTML='<span class="muted">No active transfer</span>'; else box.innerHTML=s.transfers.map(x=>`<div class="row"><b>${{x.direction==='upload'?'To Deck':'From Deck'}}:</b> ${{x.name}}<br>${{x.percent.toFixed(1)}}% • ${{fmt(x.speed)}}/s ${{x.eta?('• ETA '+Math.ceil(x.eta)+'s'):''}}<div class="bar"><div class="fill" style="width:${{Math.min(100,x.percent)}}%"></div></div></div>`).join('');}}catch(e){{}}}}
function fmt(n){{if(n>1073741824)return(n/1073741824).toFixed(1)+' GB';if(n>1048576)return(n/1048576).toFixed(1)+' MB';if(n>1024)return(n/1024).toFixed(1)+' KB';return Math.round(n)+' B'}}
let crcTable=null;
function crc32(buf){{if(!crcTable){{crcTable=new Uint32Array(256);for(let n=0;n<256;n++){{let c=n;for(let k=0;k<8;k++)c=(c&1)?(0xedb88320^(c>>>1)):(c>>>1);crcTable[n]=c>>>0;}}}}let c=0xffffffff;for(let i=0;i<buf.length;i++)c=crcTable[(c^buf[i])&255]^(c>>>8);return((c^0xffffffff)>>>0).toString(16).padStart(8,'0');}}
let uploadControl={{running:false,paused:false,cancelled:false}},queueState=[];
function renderQueue(){{let q=document.getElementById('queue');if(!queueState.length){{q.innerHTML='';return;}}q.innerHTML=queueState.map((x,i)=>`<div class="queue-item">${{i+1}}. <b>${{x.name}}</b> — ${{x.status}}</div>`).join('');}}
function setQueueStatus(i,status){{if(queueState[i]){{queueState[i].status=status;renderQueue();}}}}
function cancelledError(){{let e=new Error('Cancelled');e.cancelled=true;return e;}}
async function waitWhilePaused(){{while(uploadControl.paused&&!uploadControl.cancelled)await new Promise(resolve=>setTimeout(resolve,150));if(uploadControl.cancelled)throw cancelledError();}}
async function cancelPartial(name){{try{{await api('/api/cancel-upload',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name}})}});}}catch(e){{}}}}
async function uploadOne(f,onProgress,onRetry){{let chunk=4*1024*1024,off=0,lastName=f.name,retries=0;while(off<f.size){{try{{await waitWhilePaused();let end=Math.min(f.size,off+chunk),blob=f.slice(off,end),sum=crc32(new Uint8Array(await blob.arrayBuffer()));let r=await fetch('/upload?name='+encodeURIComponent(f.name)+'&offset='+off+'&total='+f.size,{{method:'PUT',headers:{{'Content-Type':'application/octet-stream','X-DeckyShare-CRC32':sum}},body:blob}});if(uploadControl.cancelled){{await cancelPartial(f.name);throw cancelledError();}}if(r.status===409){{let j=await r.json(),serverOff=Number(j.received||0);if(serverOff<0||serverOff>f.size)throw new Error('Invalid resume offset');off=serverOff;retries=0;onProgress(off);onRetry('Resuming from '+fmt(off));continue;}}if(r.status===422){{let j=await r.json();if(!j.checksum_mismatch)throw new Error(j.error||'Integrity check failed');off=Number(j.received||off);retries++;if(retries>3)throw new Error('Integrity check failed repeatedly');onRetry('Integrity check failed — retry '+retries+'/3');await new Promise(resolve=>setTimeout(resolve,500*retries));continue;}}if(!r.ok){{let msg=await r.text();if(r.status>=500)throw new Error(msg||('Server error '+r.status));throw new Error(msg||('Upload error '+r.status));}}let j=await r.json();off=Number(j.received||0);lastName=j.name||lastName;retries=0;onProgress(off);}}catch(e){{if(e.cancelled){{await cancelPartial(f.name);throw e;}}retries++;if(retries>3)throw e;onRetry('Connection interrupted — retry '+retries+'/3');await new Promise(resolve=>setTimeout(resolve,750*retries));}}}}return lastName;}}
document.getElementById('pause').onclick=()=>{{if(!uploadControl.running)return;uploadControl.paused=!uploadControl.paused;document.getElementById('pause').textContent=uploadControl.paused?'Resume':'Pause';document.getElementById('uptext').textContent=uploadControl.paused?'Paused — press Resume to continue':'Resuming…';}};
document.getElementById('cancel').onclick=()=>{{if(!uploadControl.running)return;uploadControl.cancelled=true;uploadControl.paused=false;document.getElementById('pause').textContent='Pause';document.getElementById('uptext').textContent='Cancelling after current chunk…';}};
document.getElementById('upload').onclick=async()=>{{let input=document.getElementById('file'),files=Array.from(input.files||[]),u=document.getElementById('uptext'),b=document.getElementById('upbar'),btn=document.getElementById('upload'),pause=document.getElementById('pause'),cancel=document.getElementById('cancel');if(!files.length||uploadControl.running)return;let total=files.reduce((n,f)=>n+f.size,0),finished=0,current=-1;queueState=files.map(f=>({{name:f.name,status:'Waiting'}}));renderQueue();uploadControl={{running:true,paused:false,cancelled:false}};btn.disabled=true;pause.disabled=false;cancel.disabled=false;try{{for(let i=0;i<files.length;i++){{current=i;if(uploadControl.cancelled)throw cancelledError();let f=files[i],label=()=>`${{i+1}}/${{files.length}} • ${{f.name}}`;setQueueStatus(i,'Uploading');await uploadOne(f,done=>{{let overall=total?((finished+done)*100/total):100;u.textContent=label()+' • '+overall.toFixed(1)+'% overall';b.style.width=Math.min(100,overall)+'%';}},status=>{{u.textContent=label()+' • '+status;}});finished+=f.size;setQueueStatus(i,'Done • verified');}}u.textContent=`Completed ${{files.length}} file${{files.length===1?'':'s'}}`;b.style.width='100%';setTimeout(()=>{{u.textContent='';b.style.width='0%';input.value='';queueState=[];renderQueue();}},1800);}}catch(e){{if(e.cancelled){{if(current>=0)setQueueStatus(current,'Cancelled');for(let i=current+1;i<queueState.length;i++)setQueueStatus(i,'Skipped');u.textContent='Transfer queue cancelled';}}else{{if(current>=0)setQueueStatus(current,'Failed');u.textContent='Upload failed after retries: '+e.message;}}}}finally{{uploadControl.running=false;uploadControl.paused=false;btn.disabled=false;pause.disabled=true;cancel.disabled=true;pause.textContent='Pause';}}}};
refresh();setInterval(refresh,700);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    server_version = "DeckyShare/1.0.5-dev"

    def log_message(self, fmt, *args):
        decky.logger.info("DeckShare HTTP: " + (fmt % args))

    def token_ok(self):
        # v1.7: stable local-network link; no per-restart URL token.
        return True

    def send_json(self, obj, status=200):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path == "/health":
            return self.send_json({"ok": True})
        if u.path == "/plugin-bootstrap":
            addr = f"http://{local_ip()}:{STATE.port}/"
            sel = None
            if STATE.selected and STATE.selected.exists():
                st = STATE.selected.stat(); sel = {"name": STATE.selected.name, "path": str(STATE.selected), "size": st.st_size, "size_human": human_size(st.st_size)}
            status = {"token": STATE.token, "address": addr, "qr": f"http://127.0.0.1:{STATE.port}/qr.svg", "selected": sel, "transfers": STATE.snapshot(), "receive_dir": str(STATE.receive_dir)}
            return self.send_json({"token": STATE.token, "roots": [{"name":n,"path":str(p)} for n,p in allowed_roots()], "status": status})
        if u.path == "/plugin-status":
            addr = f"http://{local_ip()}:{STATE.port}/"
            sel = None
            if STATE.selected and STATE.selected.exists():
                st = STATE.selected.stat(); sel = {"name": STATE.selected.name, "path": str(STATE.selected), "size": st.st_size, "size_human": human_size(st.st_size)}
            return self.send_json({"token": STATE.token, "address": addr, "qr": f"http://127.0.0.1:{STATE.port}/qr.svg", "selected": sel, "transfers": STATE.snapshot(), "receive_dir": str(STATE.receive_dir)})
        if not self.token_ok():
            self.send_error(403, "Invalid DeckShare session")
            return
        if u.path == "/":
            addr = f"http://{local_ip()}:{STATE.port}/"
            data = html_page(addr).encode()
            self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
        if u.path == "/qr.svg":
            addr = f"http://{local_ip()}:{STATE.port}/"
            data = make_qr_svg(addr)
            if not data:
                self.send_error(500, "QR unavailable"); return
            self.send_response(200); self.send_header("Content-Type","image/svg+xml"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
        if u.path == "/api/status":
            sel = None
            if STATE.selected and STATE.selected.exists():
                st = STATE.selected.stat(); sel = {"name": STATE.selected.name, "path": str(STATE.selected), "size": st.st_size, "size_human": human_size(st.st_size)}
            return self.send_json({"selected": sel, "transfers": STATE.snapshot(), "receive_dir": str(STATE.receive_dir)})
        if u.path == "/api/roots":
            return self.send_json({"roots":[{"name":n,"path":str(p)} for n,p in allowed_roots()]})
        if u.path == "/api/browse":
            q = urllib.parse.parse_qs(u.query); raw = q.get("path", [str(Path(decky.DECKY_USER_HOME))])[0]
            p = Path(raw).resolve()
            if not path_allowed(p) or not p.is_dir(): return self.send_json({"error":"Path not allowed"},403)
            items=[]
            try:
                for x in sorted(p.iterdir(), key=lambda z:(not z.is_dir(), z.name.lower())):
                    if x.name.startswith('.'):
                        continue
                    if x.is_dir(): items.append({"name":x.name,"path":str(x),"type":"dir"})
                    elif x.suffix.lower() in ALL_EXTS:
                        try: items.append({"name":x.name,"path":str(x),"type":"file","size":x.stat().st_size,"size_human":human_size(x.stat().st_size)})
                        except OSError: pass
            except OSError as e: return self.send_json({"error":str(e)},400)
            parent = str(p.parent) if path_allowed(p.parent) else None
            return self.send_json({"path":str(p),"parent":parent,"items":items})
        if u.path == "/download":
            return self.handle_download()
        self.send_error(404)

    def handle_download(self):
        p = STATE.selected
        if not p or not p.exists() or not p.is_file(): self.send_error(404,"No file selected"); return
        size=p.stat().st_size; start=0; end=size-1; ranged=False
        rh=self.headers.get("Range")
        if rh and rh.startswith("bytes="):
            try:
                a,b=rh[6:].split('-',1); start=int(a) if a else 0; end=int(b) if b else size-1; end=min(end,size-1); ranged=True
            except Exception: self.send_error(416); return
        if start<0 or start>=size or end<start: self.send_error(416); return
        length=end-start+1; tid=STATE.new_transfer("download",p.name,length)
        try:
            self.send_response(206 if ranged else 200)
            self.send_header("Content-Type",mimetypes.guess_type(p.name)[0] or "application/octet-stream")
            self.send_header("Content-Disposition",f'attachment; filename="{p.name.replace(chr(34),"")}"')
            self.send_header("Accept-Ranges","bytes")
            self.send_header("Content-Length",str(length))
            if ranged:self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
            self.end_headers(); sent=0
            with open(p,"rb",buffering=0) as f:
                f.seek(start); remain=length
                while remain:
                    chunk=f.read(min(1024*1024,remain))
                    if not chunk: break
                    self.wfile.write(chunk); sent+=len(chunk); remain-=len(chunk); STATE.update_transfer(tid,sent)
            STATE.update_transfer(tid,sent,"complete" if sent==length else "failed")
        except (BrokenPipeError,ConnectionResetError): STATE.update_transfer(tid,status="failed")
        except Exception:
            STATE.update_transfer(tid,status="failed"); raise

    def do_POST(self):
        u=urllib.parse.urlsplit(self.path)
        if not self.token_ok(): self.send_error(403); return
        if u.path=="/api/select":
            n=int(self.headers.get("Content-Length","0")); data=json.loads(self.rfile.read(n) or b"{}")
            p=Path(data.get("path","")).resolve()
            if not path_allowed(p) or not p.is_file(): return self.send_json({"error":"File not allowed"},403)
            STATE.selected=p; return self.send_json({"ok":True,"name":p.name})
        if u.path=="/api/clear-selection":
            STATE.selected=None; return self.send_json({"ok":True})
        if u.path=="/api/cancel-upload":
            n=int(self.headers.get("Content-Length","0")); data=json.loads(self.rfile.read(n) or b"{}")
            name=Path(data.get("name","")).name
            if not name: return self.send_json({"error":"Missing filename"},400)
            target=(STATE.receive_dir/name).resolve()
            if STATE.receive_dir.resolve() not in target.parents: return self.send_json({"error":"Bad filename"},400)
            part=target.with_name(target.name+".deckshare-part")
            try:
                if part.exists(): part.unlink()
            except OSError as e:
                return self.send_json({"error":str(e)},400)
            with STATE.lock:
                for tid,t in STATE.transfers.items():
                    if t["direction"]=="upload" and t["name"]==name and t["status"]=="active":
                        STATE.update_transfer(tid,status="cancelled")
            return self.send_json({"ok":True,"cancelled":name})
        self.send_error(404)

    def do_PUT(self):
        u=urllib.parse.urlsplit(self.path)
        if not self.token_ok(): self.send_error(403); return
        if u.path!="/upload": self.send_error(404); return
        q=urllib.parse.parse_qs(u.query); name=Path(q.get("name",["upload.bin"])[0]).name; offset=int(q.get("offset",["0"])[0]); total=int(q.get("total",["0"])[0]); length=int(self.headers.get("Content-Length","0"))
        target=(STATE.receive_dir/name).resolve()
        if STATE.receive_dir.resolve() not in target.parents: return self.send_json({"error":"Bad filename"},400)
        part=target.with_name(target.name+".deckshare-part")
        current=part.stat().st_size if part.exists() else 0
        if offset!=current: return self.send_json({"received":current,"resume":True},409)
        tid=None
        with STATE.lock:
            for k,t in STATE.transfers.items():
                if t["direction"]=="upload" and t["name"]==name and t["status"]=="active": tid=k; break
        if not tid: tid=STATE.new_transfer("upload",name,total)
        remain=length
        expected_crc=self.headers.get("X-DeckyShare-CRC32","").strip().lower()
        if expected_crc and (len(expected_crc)!=8 or any(c not in "0123456789abcdef" for c in expected_crc)):
            return self.send_json({"error":"Bad checksum"},400)
        crc=0
        chunk_start=current
        try:
            with open(part,"ab",buffering=0) as f:
                while remain:
                    chunk=self.rfile.read(min(1024*1024,remain))
                    if not chunk: break
                    f.write(chunk)
                    crc=crc32_update(crc,chunk)
                    remain-=len(chunk); current+=len(chunk); STATE.update_transfer(tid,current)
                actual_crc=crc32_value_hex(crc)
                if expected_crc and actual_crc!=expected_crc:
                    f.truncate(chunk_start)
                    current=chunk_start
                    STATE.update_transfer(tid,current)
                    return self.send_json({"received":current,"checksum_mismatch":True},422)
            saved_target = target
            if total and current>=total:
                saved_target = unique_destination_path(target)
                os.replace(part,saved_target)
                STATE.update_transfer(tid,current,"complete")
                item = STATE.record_received(saved_target)
                notify_file_received(item)
            return self.send_json({
                "received": current,
                "complete": bool(total and current>=total),
                "name": saved_target.name if total and current>=total else name,
                "verified": bool(expected_crc),
            })
        except Exception:
            STATE.update_transfer(tid,status="failed"); raise


def start_server():
    for port in range(PORT_START, PORT_END+1):
        try:
            server=ThreadingHTTPServer(("0.0.0.0",port),Handler); STATE.port=port; STATE.server=server
            th=threading.Thread(target=server.serve_forever,name="DeckShareHTTP",daemon=True); th.start(); STATE.thread=th
            decky.logger.info(f"DeckShare listening on {port}"); return
        except OSError: continue
    raise RuntimeError("DeckShare could not bind a port")


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
            start_server()
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
            start_server()
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
            raise ValueError("Only DeckShare received files can be deleted")
        if not p.exists() or not p.is_file():
            raise ValueError("File not found")
        p.unlink()
        with STATE.lock:
            STATE.received = [x for x in STATE.received if x.get("path") != str(p)]
        return {"ok": True, "received": STATE.received_snapshot()}

    async def ping(self, *args, **kwargs):
        if STATE.server is None:
            start_server()
        return {"ok": True, "port": STATE.port}

    async def _main(self):
        try:
            STATE.loop = asyncio.get_running_loop()
            start_server()
        except Exception:
            decky.logger.exception("DeckShare failed to start in _main; frontend bootstrap will retry")

    async def _unload(self):
        if STATE.server:
            STATE.server.shutdown()
            STATE.server.server_close()
            STATE.server = None

    async def _uninstall(self):
        pass
