from pathlib import Path
import json
import re

root = Path('build/DeckyShare')

# Backend: real removable mount discovery + non-blocking/bounded browse.
p = root / 'core_main.py'
s = p.read_text()

start = s.index('def allowed_roots():\n')
end = s.index('\n\ndef path_allowed(path):\n', start)
allowed = '''def allowed_roots():
    home = Path(decky.DECKY_USER_HOME).resolve()
    roots = []
    for name, path in [
        ("Home", home),
        ("Videos", home / "Videos"),
        ("Downloads", home / "Downloads"),
        ("Desktop", home / "Desktop"),
    ]:
        try:
            if path.exists():
                roots.append((name, path.resolve()))
        except OSError:
            pass

    media_mounts = []
    try:
        text = Path("/proc/self/mountinfo").read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            raw = parts[4]
            mount = (raw.replace("\\\\040", " ")
                        .replace("\\\\011", "\\t")
                        .replace("\\\\012", "\\n")
                        .replace("\\\\134", "\\\\"))
            if mount.startswith("/run/media/"):
                q = Path(mount)
                if q not in media_mounts:
                    media_mounts.append(q)
    except OSError:
        media_mounts = []

    for q in media_mounts:
        prefix = str(q).rstrip("/") + "/"
        if q.name == home.name and any(str(other).startswith(prefix) for other in media_mounts if other != q):
            continue
        roots.append((f"Drive: {q.name}", q))

    out = []
    seen = set()
    for name, path in roots:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append((name, path))
    return out'''
s = s[:start] + allowed + s[end:]

start = s.index('def browse_info(path):\n')
end = s.index('\n\ndef _fm_path(v):\n', start)
browse = '''def browse_info(path):
    p = Path(path).expanduser().resolve()
    if not path_allowed(p) or not p.is_dir():
        raise ValueError("Folder not allowed")

    rows = []
    try:
        with os.scandir(p) as scan:
            for entry in scan:
                if len(rows) >= 300:
                    break
                try:
                    if entry.is_symlink():
                        continue
                    is_dir = entry.is_dir(follow_symlinks=False)
                    is_file = entry.is_file(follow_symlinks=False)
                    if not is_dir and not is_file:
                        continue
                    st = entry.stat(follow_symlinks=False)
                    rows.append((is_dir, entry.name, st))
                except OSError:
                    continue
    except (PermissionError, OSError):
        raise ValueError("Folder cannot be opened")

    rows.sort(key=lambda row: (not row[0], row[1].lower()))
    items = []
    for is_dir, name, st in rows:
        child = p / name
        if is_dir:
            items.append({"type": "dir", "name": name, "path": str(child), "mtime": st.st_mtime})
        else:
            items.append({"type": "file", "name": name, "path": str(child), "size": st.st_size, "size_human": human_size(st.st_size), "mtime": st.st_mtime})

    parent = None
    pp = p.parent
    if pp != p and path_allowed(pp):
        parent = str(pp)

    storage = None
    if not str(p).startswith("/run/media/"):
        try:
            du = shutil.disk_usage(p)
            storage = {"total": du.total, "used": du.used, "free": du.free,
                       "total_human": human_size(du.total), "used_human": human_size(du.used),
                       "free_human": human_size(du.free)}
        except OSError:
            storage = None

    return {"path": str(p), "parent": parent, "items": items, "storage": storage}'''
s = s[:start] + browse + s[end:]

old = '''    async def browse(self, path=None, *args, **kwargs):
        p = extract_path(path, args, kwargs)
        if not p:
            raise ValueError("Missing folder path")
        return browse_info(p)
'''
new = '''    async def browse(self, path=None, *args, **kwargs):
        p = extract_path(path, args, kwargs)
        if not p:
            raise ValueError("Missing folder path")
        try:
            return await asyncio.wait_for(asyncio.to_thread(browse_info, p), timeout=3.0)
        except asyncio.TimeoutError:
            raise ValueError("Folder is taking too long to open. The drive may be busy or unavailable")
'''
if old not in s:
    raise SystemExit('browse RPC marker missing')
s = s.replace(old, new, 1)
p.write_text(s)

# Frontend: replace unreliable Game Mode select with real buttons.
p = root / 'dist' / 'index.js'
s = p.read_text()
old = '''          h("div",{style:{display:"grid",gridTemplateColumns:"1fr 96px",gap:6,marginBottom:7}},
            h("input",{value:browseQuery,onChange:e=>setBrowseQuery(e.target.value),placeholder:"Search this folder",style:{minWidth:0,width:"100%",boxSizing:"border-box",padding:"9px 10px",borderRadius:10,border:"1px solid rgba(120,180,255,.18)",background:"rgba(7,17,29,.48)",color:"white",fontSize:11,outline:"none"}}),
            h("select",{value:browseSort,onChange:e=>setBrowseSort(e.target.value),style:{width:"100%",padding:"8px 6px",borderRadius:10,border:"1px solid rgba(120,180,255,.18)",background:"#14263c",color:"white",fontSize:10}},
              h("option",{value:"name"},"Name"),
              h("option",{value:"date"},"Newest"),
              h("option",{value:"size"},"Largest")
            )
          ),'''
new = '''          h("div",{style:{display:"grid",gap:6,marginBottom:7}},
            h("input",{value:browseQuery,onChange:e=>setBrowseQuery(e.target.value),placeholder:"Search this folder",style:{minWidth:0,width:"100%",boxSizing:"border-box",padding:"9px 10px",borderRadius:10,border:"1px solid rgba(120,180,255,.18)",background:"rgba(7,17,29,.48)",color:"white",fontSize:11,outline:"none"}}),
            h("div",{style:{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:5}},
              [["name","Name"],["date","Newest"],["size","Largest"]].map(([value,label])=>h("button",{key:value,onClick:()=>setBrowseSort(value),style:{padding:"7px 5px",borderRadius:9,border:browseSort===value?"1px solid #66c0f4":"1px solid rgba(120,180,255,.16)",background:browseSort===value?"rgba(102,192,244,.15)":"rgba(255,255,255,.025)",color:browseSort===value?"#bde7ff":"#d9edff",fontSize:10,fontWeight:700}},label))
            )
          ),'''
if old not in s:
    raise SystemExit('sort select marker missing')
s = s.replace(old, new, 1)
if '"RC11"' in s:
    s = s.replace('"RC11"', '"RC11.1"', 1)
p.write_text(s)

p = root / 'package.json'
data = json.loads(p.read_text())
data['version'] = '1.1.0-rc.11.1'
p.write_text(json.dumps(data, indent=2) + '\n')

p = root / 'main.py'
s = p.read_text()
s = re.sub(r'_core\.Handler\.server_version = "DeckyShare/[^"]+"', '_core.Handler.server_version = "DeckyShare/1.1.0-rc11.1"', s, count=1)
p.write_text(s)
