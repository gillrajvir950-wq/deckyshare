from pathlib import Path
import json,re
root=Path('build/DeckyShare'); p=root/'dist/index.js'; s=p.read_text()
marker='[fmTrashArmed,setFmTrashArmed]=useState(false),[browseLimit,setBrowseLimit]=useState(50);'
assert marker in s
s=s.replace(marker,'[fmTrashArmed,setFmTrashArmed]=useState(false),[browseLimit,setBrowseLimit]=useState(50),[fmLocationsOpen,setFmLocationsOpen]=useState(false),[fmStorageOpen,setFmStorageOpen]=useState(false),[fmSortOpen,setFmSortOpen]=useState(false);',1)
anchor=s.index('):path&&h("div",null,')
a=s.index('          h("div",{style:{display:"flex",gap:6,flexWrap:"wrap",marginBottom:7}},',anchor); b=s.index('          fmNew&&h("div"',a)
top='''          h("div",{style:{display:"grid",gridTemplateColumns:"auto 1fr auto auto",gap:5,alignItems:"center",marginBottom:7}},
            parent&&h("button",{onClick:()=>browse(parent),style:{padding:"7px 9px",borderRadius:9,border:"1px solid rgba(120,180,255,.14)",background:"rgba(255,255,255,.025)",color:"#d9edff",fontWeight:800}},"←"),
            h("div",{style:{minWidth:0,fontSize:10,fontWeight:760,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",padding:"0 3px"}},browseCrumbs.length?browseCrumbs.map(c=>c.label).join(" › "):"Files"),
            h("button",{onClick:()=>{setFmSelect(v=>!v);setFmPicked([]);setFmInfo(null);},style:{padding:"7px 9px",borderRadius:9,border:fmSelect?"1px solid #66c0f4":"1px solid rgba(120,180,255,.14)",background:fmSelect?"rgba(102,192,244,.14)":"rgba(255,255,255,.025)",color:"#d9edff",fontSize:10,fontWeight:760}},fmSelect?"Done":"Select"),
            h("button",{onClick:()=>setFmNew(fmNew?"":"New folder"),style:{width:34,height:34,borderRadius:9,border:"1px solid rgba(120,180,255,.14)",background:"rgba(255,255,255,.025)",color:"#d9edff",fontSize:18,fontWeight:700}},fmNew?"×":"+")
          ),
          fmStorage&&h("button",{onClick:()=>setFmStorageOpen(v=>!v),style:{width:"100%",textAlign:"left",padding:"5px 7px",marginBottom:6,borderRadius:8,border:"1px solid rgba(120,180,255,.08)",background:"rgba(255,255,255,.015)",color:"white",fontSize:9,opacity:.65}},fmStorageOpen?`${fmStorage.used_human} used • ${fmStorage.free_human} free ▲`:`Storage • ${fmStorage.free_human} free ▼`),
          fmStorage&&fmStorageOpen&&h("div",{style:{margin:"-2px 3px 7px"}},h(Bar,{value:fmUsed})),
'''
s=s[:a]+top+s[b:]
a=s.index('          h("div",{style:{display:"flex",gap:4,alignItems:"center",flexWrap:"wrap",padding:"7px 8px"',s.index('fmInfo&&h')); b=s.index('          h("div",{style:{fontSize:9,opacity:.42,margin:"4px 1px 7px"}',a)
controls='''          h("div",{style:{display:"grid",gridTemplateColumns:"1fr auto auto",gap:5,marginBottom:7}},
            h("input",{value:browseQuery,onChange:e=>{setBrowseQuery(e.target.value);setBrowseLimit(50);},placeholder:"Search files…",style:{minWidth:0,width:"100%",boxSizing:"border-box",padding:"9px 10px",borderRadius:10,border:"1px solid rgba(120,180,255,.18)",background:"rgba(7,17,29,.48)",color:"white",fontSize:11,outline:"none"}}),
            h("button",{onClick:()=>setFmSortOpen(v=>!v),style:{padding:"7px 9px",borderRadius:9,border:"1px solid rgba(120,180,255,.14)",background:"rgba(255,255,255,.025)",color:"#d9edff",fontSize:10,fontWeight:760,whiteSpace:"nowrap"}},`Sort: ${browseSort==="date"?"Newest":browseSort==="size"?"Largest":"Name"} ▾`),
            h("button",{onClick:()=>setFmLocationsOpen(v=>!v),style:{padding:"7px 9px",borderRadius:9,border:"1px solid rgba(120,180,255,.14)",background:"rgba(255,255,255,.025)",color:"#d9edff",fontSize:10,fontWeight:760}},"Locations")
          ),
          fmSortOpen&&h("div",{style:{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:5,marginBottom:7}},[["name","Name"],["date","Newest"],["size","Largest"]].map(([value,label])=>h("button",{key:value,onClick:()=>{setBrowseSort(value);setBrowseLimit(50);setFmSortOpen(false);},style:{padding:"7px 5px",borderRadius:9,border:browseSort===value?"1px solid #66c0f4":"1px solid rgba(120,180,255,.12)",background:browseSort===value?"rgba(102,192,244,.14)":"rgba(255,255,255,.02)",color:"#d9edff",fontSize:10,fontWeight:700}},label))),
          fmLocationsOpen&&h("div",{style:{display:"flex",gap:4,overflowX:"auto",paddingBottom:6,marginBottom:4}},roots.map(r=>h("button",{key:r.path,onClick:()=>{setFmLocationsOpen(false);browse(r.path);},style:{flex:"0 0 auto",padding:"6px 8px",borderRadius:999,border:path===r.path?"1px solid #66c0f4":"1px solid rgba(120,180,255,.14)",background:path===r.path?"rgba(102,192,244,.13)":"rgba(255,255,255,.025)",color:"#d9edff",fontSize:9,fontWeight:700}},r.name.startsWith("Drive:")?`💾 ${r.name.replace("Drive: ","")}`:r.name))),
'''
s=s[:a]+controls+s[b:]
s=s.replace('"RC11.2"','"RC11.3"',1); p.write_text(s)
pkg=root/'package.json'; d=json.loads(pkg.read_text()); d['version']='1.1.0-rc.11.3'; pkg.write_text(json.dumps(d,indent=2)+'\n')
mp=root/'main.py'; ms=mp.read_text(); ms=re.sub(r'_core\.Handler\.server_version = "DeckyShare/[^"]+"','_core.Handler.server_version = "DeckyShare/1.1.0-rc11.3"',ms,count=1); mp.write_text(ms)
assert 'Search files…' in s and 'fmSortOpen' in s and 'fmLocationsOpen' in s and 'Storage •' in s
assert 'Search this folder' not in s
print('RC11.3 UI patch OK')
