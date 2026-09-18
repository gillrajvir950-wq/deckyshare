from pathlib import Path
import json
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "build/DeckyShare")
ui_path = root / "dist/index.js"
s = ui_path.read_text()

start_marker = 'visibleBrowseItems.slice(0,browseLimit).map(it=>h("button"'
tail_marker = '          visibleBrowseItems.length>browseLimit&&h("button"'
start = s.find(start_marker)
if start < 0:
    raise SystemExit("compact-row start marker missing")
tail = s.find(tail_marker, start)
if tail < 0:
    raise SystemExit("compact-row tail marker missing")

compact_rows = '''visibleBrowseItems.slice(0,browseLimit).map(it=>h("button",{key:it.path,onClick:()=>fmSelect?fmToggle(it):(it.type==="dir"?browse(it.path):selectFile(it.path)),onFocus:e=>{e.currentTarget.style.borderColor="#66c0f4";e.currentTarget.style.background="rgba(35,72,108,.68)";},onBlur:e=>{const picked=fmPicked.includes(it.path);e.currentTarget.style.borderColor=picked?"#66c0f4":"rgba(120,180,255,.11)";e.currentTarget.style.background=picked?"rgba(48,92,132,.68)":"rgba(20,39,63,.46)";},style:{width:"100%",padding:"5px 7px",margin:"2px 0",borderRadius:9,border:fmPicked.includes(it.path)?"1px solid #66c0f4":"1px solid rgba(120,180,255,.11)",background:fmPicked.includes(it.path)?"rgba(48,92,132,.68)":"rgba(20,39,63,.46)",boxShadow:fmPicked.includes(it.path)?"inset 3px 0 0 #66c0f4":"none",color:"white",textAlign:"left",transition:"background .12s ease,border-color .12s ease"}},
            h("div",{style:{display:"grid",gridTemplateColumns:"26px minmax(0,1fr) 18px",gap:7,alignItems:"center"}},
              h("div",{style:{width:26,height:26,borderRadius:7,display:"flex",alignItems:"center",justifyContent:"center",background:it.type==="dir"?"rgba(102,192,244,.09)":"rgba(255,255,255,.04)",fontSize:14,flexShrink:0}},browseFileIcon(it)),
              h("div",{style:{minWidth:0}},
                h("div",{style:{fontWeight:720,fontSize:10,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}},it.name),
                h("div",{style:{fontSize:9,opacity:.46,marginTop:1,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}},browseDate(it.mtime)||(it.type==="dir"?"Folder":""))
              ),
              h("div",{style:{fontSize:14,lineHeight:1,textAlign:"center",fontWeight:850,color:fmSelect&&fmPicked.includes(it.path)?"#9edcff":"#70869a",opacity:fmSelect||it.type==="dir"?1:.35}},fmSelect?(fmPicked.includes(it.path)?"✓":"○"):(it.type==="dir"?"›":""))
            )
          )),
'''
s = s[:start] + compact_rows + s[tail:]

if '"RC11.3"' not in s:
    raise SystemExit("RC11.3 UI badge missing")
s = s.replace('"RC11.3"', '"RC11.4"', 1)
ui_path.write_text(s)

pkg_path = root / "package.json"
pkg = json.loads(pkg_path.read_text())
pkg["version"] = "1.1.0-rc.11.4"
pkg_path.write_text(json.dumps(pkg, indent=2) + "\n")

main_path = root / "main.py"
ms = main_path.read_text()
ms, n = re.subn(
    r'_core\.Handler\.server_version = "DeckyShare/[^"]+"',
    '_core.Handler.server_version = "DeckyShare/1.1.0-rc11.4"',
    ms,
    count=1,
)
if n != 1:
    raise SystemExit("server version marker missing")
main_path.write_text(ms)

print("RC11.4 compact-row patch applied")
