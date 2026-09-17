from pathlib import Path
import json,re,sys
root=Path(sys.argv[1])

# Backend file operations
p=root/'core_main.py'; s=p.read_text()
if 'import shutil\n' not in s: s=s.replace('import os\n','import os\nimport shutil\n',1)
s=s.replace('elif child.is_file() and child.suffix.lower() in ALL_EXTS:','elif child.is_file():')
old='    return {"path": str(p), "parent": parent, "items": items}\n\n\ndef qr_data_uri(address):'
if old not in s: raise SystemExit('browse marker')
ops=r'''    du = shutil.disk_usage(p)
    return {"path": str(p), "parent": parent, "items": items, "storage": {"total":du.total,"used":du.used,"free":du.free,"total_human":human_size(du.total),"used_human":human_size(du.used),"free_human":human_size(du.free)}}


def _fm_path(v):
    if not v: raise ValueError("Missing path")
    q=Path(str(v)).expanduser()
    if q.is_symlink(): raise ValueError("Symlinks are not managed")
    q=q.resolve()
    if not path_allowed(q) or not q.exists(): raise ValueError("Item not allowed or missing")
    return q


def _fm_root(q): return any(Path(q).resolve()==r for _,r in allowed_roots())
def _fm_name(v):
    n=str(v or "").strip()
    if not n or n in (".","..") or Path(n).name!=n or "/" in n or "\\" in n: raise ValueError("Invalid name")
    return n

def _fm_unique(parent,name,is_dir=False):
    t=Path(parent)/name
    if not t.exists(): return t
    q=Path(name); stem=name if is_dir else (q.stem or q.name); suffix="" if is_dir else q.suffix
    for i in range(1,10000):
        t=Path(parent)/f"{stem} ({i}){suffix}"
        if not t.exists(): return t
    raise ValueError("No free destination name")

def _fm_item(q):
    q=Path(q); st=q.stat(); d=q.is_dir()
    return {"name":q.name,"path":str(q),"type":"dir" if d else "file","size":0 if d else st.st_size,"size_human":"Folder" if d else human_size(st.st_size),"mtime":st.st_mtime,"mime":None if d else (mimetypes.guess_type(q.name)[0] or "application/octet-stream")}

def _fm_sources(paths):
    if not isinstance(paths,list) or not paths: raise ValueError("Select at least one item")
    out=[]
    for v in paths[:100]:
        q=_fm_path(v)
        if _fm_root(q): raise ValueError("Quick locations cannot be modified")
        if q not in out: out.append(q)
    return out

def _fm_mkdir(parent,name):
    d=_fm_path(parent)
    if not d.is_dir(): raise ValueError("Destination is not a folder")
    t=(d/_fm_name(name)).resolve()
    if not path_allowed(t) or t.exists(): raise ValueError("Folder already exists or is not allowed")
    t.mkdir(); return {"ok":True,"item":_fm_item(t)}

def _fm_rename(path,name):
    q=_fm_path(path)
    if _fm_root(q): raise ValueError("Quick locations cannot be renamed")
    t=(q.parent/_fm_name(name)).resolve()
    if not path_allowed(t) or t.exists(): raise ValueError("Name already exists or is not allowed")
    q.rename(t)
    if STATE.selected and Path(STATE.selected).resolve()==q: STATE.selected=t if t.is_file() else None
    return {"ok":True,"item":_fm_item(t)}

def _fm_copy_move(paths,dest,move=False):
    dst=_fm_path(dest)
    if not dst.is_dir(): raise ValueError("Destination is not a folder")
    done=[]
    for q in _fm_sources(paths):
        if q.is_dir():
            try: dst.relative_to(q); raise ValueError("Cannot paste a folder inside itself")
            except ValueError as e:
                if str(e)=="Cannot paste a folder inside itself": raise
        if move and q.parent==dst: done.append(_fm_item(q)); continue
        t=_fm_unique(dst,q.name,q.is_dir())
        if move:
            shutil.move(str(q),str(t))
            if STATE.selected and Path(STATE.selected).resolve()==q: STATE.selected=t if t.is_file() else None
        elif q.is_dir(): shutil.copytree(q,t,symlinks=True)
        else: shutil.copy2(q,t)
        done.append(_fm_item(t))
    return {"ok":True,"items":done}

def _fm_trash(paths):
    base=Path(decky.DECKY_USER_HOME).resolve()/".local/share/Trash"; files=base/'files'; info=base/'info'; files.mkdir(parents=True,exist_ok=True); info.mkdir(parents=True,exist_ok=True)
    for q in _fm_sources(paths):
        src=str(q); t=_fm_unique(files,q.name,q.is_dir()); shutil.move(src,str(t)); (info/(t.name+'.trashinfo')).write_text('[Trash Info]\\nPath='+urllib.parse.quote(src,safe='/')+'\\nDeletionDate='+time.strftime('%Y-%m-%dT%H:%M:%S')+'\\n')
        if STATE.selected and Path(STATE.selected).resolve()==Path(src).resolve(): STATE.selected=None
    return {"ok":True}

def _fm_details(path):
    q=_fm_path(path); item=_fm_item(q)
    if q.is_dir():
        try: item['item_count']=sum(1 for x in q.iterdir() if not x.name.startswith('.'))
        except OSError: item['item_count']=None
    return {"ok":True,"item":item}


def qr_data_uri(address):'''
s=s.replace(old,ops,1)
mark='    async def ping(self, *args, **kwargs):\n'
if mark not in s: raise SystemExit('plugin marker')
methods=r'''    async def file_mkdir(self,payload=None,*args,**kwargs):
        d=payload if isinstance(payload,dict) else kwargs; return await asyncio.to_thread(_fm_mkdir,d.get("parent"),d.get("name"))
    async def file_rename(self,payload=None,*args,**kwargs):
        d=payload if isinstance(payload,dict) else kwargs; return await asyncio.to_thread(_fm_rename,d.get("path"),d.get("name"))
    async def file_copy(self,payload=None,*args,**kwargs):
        d=payload if isinstance(payload,dict) else kwargs; return await asyncio.to_thread(_fm_copy_move,d.get("paths"),d.get("destination"),False)
    async def file_move(self,payload=None,*args,**kwargs):
        d=payload if isinstance(payload,dict) else kwargs; return await asyncio.to_thread(_fm_copy_move,d.get("paths"),d.get("destination"),True)
    async def file_trash(self,payload=None,*args,**kwargs):
        d=payload if isinstance(payload,dict) else kwargs; return await asyncio.to_thread(_fm_trash,d.get("paths"))
    async def file_details(self,payload=None,*args,**kwargs):
        d=payload if isinstance(payload,dict) else kwargs; return await asyncio.to_thread(_fm_details,d.get("path"))

'''
s=s.replace(mark,methods+mark,1); p.write_text(s)

# Frontend augment existing Browse Files
p=root/'dist/index.js'; s=p.read_text()
state='[browseQuery,setBrowseQuery]=useState(""),[browseSort,setBrowseSort]=useState("name");'
repl='[browseQuery,setBrowseQuery]=useState(""),[browseSort,setBrowseSort]=useState("name"),[fmStorage,setFmStorage]=useState(null),[fmSelect,setFmSelect]=useState(false),[fmPicked,setFmPicked]=useState([]),[fmClip,setFmClip]=useState(null),[fmBusy,setFmBusy]=useState(false),[fmNew,setFmNew]=useState(""),[fmRename,setFmRename]=useState(null),[fmRenameValue,setFmRenameValue]=useState(""),[fmInfo,setFmInfo]=useState(null),[fmTrashArmed,setFmTrashArmed]=useState(false);'
if state not in s: raise SystemExit('state')
s=s.replace(state,repl,1)
oldbrowse='async function browse(p){try{const j=await call("browse",{path:p});setPath(j.path);setParent(j.parent);setItems(j.items||[]);setBrowseQuery("");setErr("");}catch(e){setErr("Browse: "+String(e&&e.message||e));}}'
newbrowse='async function browse(p){try{const j=await call("browse",{path:p});setPath(j.path);setParent(j.parent);setItems(j.items||[]);setFmStorage(j.storage||null);setBrowseQuery("");setFmPicked([]);setFmSelect(false);setFmInfo(null);setFmRename(null);setErr("");}catch(e){setErr("Browse: "+String(e&&e.message||e));}}'
if oldbrowse not in s: raise SystemExit('browse fn')
s=s.replace(oldbrowse,newbrowse,1)
insert='    async function copyToClipboard(text){\n'
if insert not in s: raise SystemExit('insert fn')
funcs=r'''    function fmToggle(it){setFmSelect(true);setFmInfo(null);setFmPicked(v=>v.includes(it.path)?v.filter(x=>x!==it.path):[...v,it.path]);}
    async function fmMkdir(){if(!path||!fmNew.trim()||fmBusy)return;setFmBusy(true);try{await call("file_mkdir",{parent:path,name:fmNew.trim()});setFmNew("");await browse(path);}catch(e){setErr("New folder: "+String(e&&e.message||e));}finally{setFmBusy(false);}}
    function fmStage(mode){if(fmPicked.length){setFmClip({mode,paths:fmPicked.slice()});setFmPicked([]);setFmSelect(false);}}
    async function fmPaste(){if(!fmClip||!path||fmBusy)return;const c=fmClip;setFmBusy(true);try{await call(c.mode==="move"?"file_move":"file_copy",{paths:c.paths,destination:path});setFmClip(null);await browse(path);}catch(e){setErr("Paste: "+String(e&&e.message||e));}finally{setFmBusy(false);}}
    async function fmDoRename(){if(!fmRename||!fmRenameValue.trim()||fmBusy)return;setFmBusy(true);try{await call("file_rename",{path:fmRename.path,name:fmRenameValue.trim()});setFmRename(null);setFmRenameValue("");await browse(path);}catch(e){setErr("Rename: "+String(e&&e.message||e));}finally{setFmBusy(false);}}
    async function fmDetails(it){try{const r=await call("file_details",{path:it.path});setFmInfo(r.item||null);}catch(e){setErr("Details: "+String(e&&e.message||e));}}
    async function fmTrash(){if(!fmPicked.length||fmBusy)return;if(!fmTrashArmed){setFmTrashArmed(true);setTimeout(()=>setFmTrashArmed(false),7000);return;}setFmBusy(true);try{await call("file_trash",{paths:fmPicked});setFmPicked([]);setFmSelect(false);setFmTrashArmed(false);await browse(path);await refreshStatus();}catch(e){setErr("Trash: "+String(e&&e.message||e));}finally{setFmBusy(false);}}

'''
s=s.replace(insert,funcs+insert,1)
der='    const visibleBrowseItems=path?browseVisibleItems(items,browseQuery,browseSort):[];\n'
if der not in s: raise SystemExit('derived')
s=s.replace(der,der+'    const fmChosen=items.filter(x=>fmPicked.includes(x.path));\n    const fmUsed=fmStorage&&fmStorage.total?(fmStorage.used*100/fmStorage.total):0;\n',1)
# Toolbar: add manager controls after Up.
tool='            parent&&h(MiniButton,{onClick:()=>browse(parent)},"↑ Up")\n          ),'
if tool not in s: raise SystemExit('toolbar')
newtool='''            parent&&h(MiniButton,{onClick:()=>browse(parent)},"↑ Up"),
            h(MiniButton,{onClick:()=>{setFmSelect(v=>!v);setFmPicked([]);setFmInfo(null);}},fmSelect?"Done":"Select"),
            h(MiniButton,{onClick:()=>setFmNew(fmNew?"":"New folder")},fmNew?"Cancel folder":"＋ New folder")
          ),
          fmStorage&&h("div",{style:{fontSize:9,opacity:.55,marginBottom:6}},`${fmStorage.used_human} used • ${fmStorage.free_human} free`,h(Bar,{value:fmUsed})),
          fmNew&&h("div",{style:{display:"grid",gridTemplateColumns:"1fr auto",gap:6,marginBottom:7}},h("input",{value:fmNew==="New folder"?"":fmNew,onChange:e=>setFmNew(e.target.value),placeholder:"Folder name",style:{minWidth:0,padding:"8px",borderRadius:8,background:"#0c1a2b",color:"white",border:"1px solid rgba(120,180,255,.18)"}}),h(MiniButton,{onClick:fmMkdir},"Create")),
          fmClip&&h("div",{style:{padding:7,borderRadius:9,marginBottom:7,background:"rgba(255,190,75,.08)",border:"1px solid rgba(255,190,75,.20)"}},h("div",{style:{fontSize:10,marginBottom:5}},`${fmClip.mode==="move"?"Move":"Copy"} ${fmClip.paths.length} item(s) here?`),h("div",{style:{display:"flex",gap:5}},h(MiniButton,{onClick:fmPaste},"Paste here"),h(MiniButton,{onClick:()=>setFmClip(null)},"Cancel"))),
          fmRename&&h("div",{style:{display:"grid",gridTemplateColumns:"1fr auto",gap:6,marginBottom:7}},h("input",{value:fmRenameValue,onChange:e=>setFmRenameValue(e.target.value),style:{minWidth:0,padding:"8px",borderRadius:8,background:"#0c1a2b",color:"white",border:"1px solid rgba(120,180,255,.18)"}}),h(MiniButton,{onClick:fmDoRename},"Rename")),
          fmInfo&&h("div",{style:{padding:8,borderRadius:9,marginBottom:7,background:"rgba(255,255,255,.025)",border:"1px solid rgba(120,180,255,.12)",fontSize:9}},h("div",{style:{fontWeight:760,fontSize:11}},`${browseFileIcon(fmInfo)} ${fmInfo.name}`),h("div",{style:{opacity:.55,wordBreak:"break-all",marginTop:3}},fmInfo.path),h("div",{style:{opacity:.55,marginTop:2}},fmInfo.type==="dir"?`Folder${fmInfo.item_count!=null?` • ${fmInfo.item_count} item(s)`:""}`:`${fmInfo.size_human}${fmInfo.mime?` • ${fmInfo.mime}`:""}`)),'''
s=s.replace(tool,newtool,1)
# Turn file rows into multi-select rows when Select is active.
row='!visibleBrowseItems.length?h("div",{style:{padding:"15px 8px",textAlign:"center",fontSize:11,opacity:.5,border:"1px dashed rgba(120,180,255,.14)",borderRadius:10}},browseQuery?"No matching files in this folder":"This folder has no supported files"):visibleBrowseItems.slice(0,150).map(it=>h("button",{key:it.path,onClick:()=>it.type==="dir"?browse(it.path):selectFile(it.path),style:{width:"100%",padding:"8px 9px",margin:"4px 0",borderRadius:11,border:"1px solid rgba(120,180,255,.11)",background:"rgba(20,39,63,.56)",color:"white",textAlign:"left"}},'
if row not in s: raise SystemExit('row')
rownew='!visibleBrowseItems.length?h("div",{style:{padding:"15px 8px",textAlign:"center",fontSize:11,opacity:.5,border:"1px dashed rgba(120,180,255,.14)",borderRadius:10}},browseQuery?"No matching items in this folder":"This folder is empty"):visibleBrowseItems.slice(0,150).map(it=>h("button",{key:it.path,onClick:()=>fmSelect?fmToggle(it):(it.type==="dir"?browse(it.path):selectFile(it.path)),style:{width:"100%",padding:"8px 9px",margin:"4px 0",borderRadius:11,border:fmPicked.includes(it.path)?"1px solid #66c0f4":"1px solid rgba(120,180,255,.11)",background:fmPicked.includes(it.path)?"rgba(48,92,132,.72)":"rgba(20,39,63,.56)",color:"white",textAlign:"left"}},fmSelect&&h("span",{style:{display:"inline-block",width:22,fontWeight:900,color:fmPicked.includes(it.path)?"#9edcff":"#657b91"}},fmPicked.includes(it.path)?"✓":"○"),'
s=s.replace(row,rownew,1)
# Sticky action bar after the 150-items note.
note='          visibleBrowseItems.length>150&&h("div",{style:{fontSize:9,opacity:.42,textAlign:"center",paddingTop:5}},`Showing first 150 of ${visibleBrowseItems.length} items`)\n        )'
if note not in s: raise SystemExit('note')
actions='''          visibleBrowseItems.length>150&&h("div",{style:{fontSize:9,opacity:.42,textAlign:"center",paddingTop:5}},`Showing first 150 of ${visibleBrowseItems.length} items`),
          fmSelect&&fmChosen.length>0&&h("div",{style:{position:"sticky",bottom:4,zIndex:3,padding:8,marginTop:8,borderRadius:10,background:"rgba(9,22,38,.97)",border:"1px solid rgba(102,192,244,.28)"}},h("div",{style:{fontSize:10,fontWeight:760,marginBottom:5}},`${fmChosen.length} selected`),h("div",{style:{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:5}},h(MiniButton,{onClick:()=>fmStage("copy")},"Copy"),h(MiniButton,{onClick:()=>fmStage("move")},"Move"),h(MiniButton,{onClick:()=>{if(fmChosen.length===1){setFmRename(fmChosen[0]);setFmRenameValue(fmChosen[0].name);}else setErr("Rename: select one item");}},"Rename"),h(MiniButton,{onClick:()=>fmChosen.length===1?fmDetails(fmChosen[0]):setErr("Details: select one item")},"Details"),h(MiniButton,{onClick:()=>{if(fmChosen.length===1&&fmChosen[0].type==="file")selectFile(fmChosen[0].path);else setErr("Share: select one file");}},"Share"),h(MiniButton,{onClick:fmTrash,tone:"danger"},fmTrashArmed?"Tap again":"Trash")))
        )'''
s=s.replace(note,actions,1)
s=s.replace('"RC10.1"','"RC11"',1)
p.write_text(s)

# Versions
p=root/'package.json'; d=json.loads(p.read_text()); d['version']='1.1.0-rc.11'; p.write_text(json.dumps(d,indent=2)+'\n')
p=root/'main.py'; x=p.read_text(); x=re.sub(r'_core\.Handler\.server_version = "DeckyShare/[^"]+"','_core.Handler.server_version = "DeckyShare/1.1.0-rc11"',x,count=1); p.write_text(x)
print('RC11 patch applied')