// @ts-nocheck
const React = window.SP_REACT || window.React;
const h = React.createElement;
const { useEffect, useMemo, useRef, useState } = React;
const DeckyUI = window.DFL || {};
const DialogButton = DeckyUI.DialogButton || "button";
const Focusable = DeckyUI.Focusable || "div";
const TextField = DeckyUI.TextField || "input";

const NOTIFY_KEY = "deckyshare.notifications";
const NOTIFY_TTL = 4000;
const notifySeen = new Map();
let receivedBatch = [];
let receivedBatchTimer = null;

function fmt(n){
  if(!Number.isFinite(n)) return "0 B";
  if(n>=1073741824) return (n/1073741824).toFixed(1)+" GB";
  if(n>=1048576) return (n/1048576).toFixed(1)+" MB";
  if(n>=1024) return (n/1024).toFixed(1)+" KB";
  return Math.round(n)+" B";
}
function notificationsEnabled(){try{return window.localStorage.getItem(NOTIFY_KEY)!=="off";}catch(e){return true;}}
function saveNotificationsEnabled(v){try{window.localStorage.setItem(NOTIFY_KEY,v?"on":"off");}catch(e){}}
function unwrap(item){return item&&item.result||item&&item.data||item||{};}
function notifyKey(type,item){const p=unwrap(item);return `${type}:${p.path||p.id||p.name||"unknown"}`;}
function shouldNotify(type,item){
  if(!notificationsEnabled()) return false;
  const now=Date.now(),key=notifyKey(type,item),prev=notifySeen.get(key);
  for(const [k,t] of notifySeen){if(now-t>=NOTIFY_TTL)notifySeen.delete(k);}
  if(prev!=null&&now-prev<NOTIFY_TTL)return false;
  notifySeen.set(key,now);return true;
}
function toast(api,body){
  try{if(api&&api.toaster&&typeof api.toaster.toast==="function")api.toaster.toast({title:"DeckyShare",body});}
  catch(e){console.error("[DeckyShare] toast failed",e);}
}
function flushReceivedBatch(api){
  const batch=receivedBatch.splice(0);
  receivedBatchTimer=null;
  if(!batch.length||!notificationsEnabled())return;
  if(batch.length===1){const p=batch[0];toast(api,`Received: ${p.name||"file"}\nSaved to: ${p.path||"Downloads/DeckShare"}`);return;}
  const names=batch.slice(0,3).map(x=>x.name||"file").join(", ");
  const more=batch.length>3?` +${batch.length-3} more`:"";
  toast(api,`Received ${batch.length} files\n${names}${more}`);
}
function queueReceivedToast(api,item){
  if(!item||!shouldNotify("received",item))return;
  const p=unwrap(item);
  if(!receivedBatch.some(x=>(x.path||x.name)===(p.path||p.name)))receivedBatch.push(p);
  if(receivedBatchTimer)clearTimeout(receivedBatchTimer);
  receivedBatchTimer=setTimeout(()=>flushReceivedBatch(api),900);
}
function showTransferResult(api,t){
  if(!t||!t.id)return;
  if(t.status==="failed"&&shouldNotify("failed",t))toast(api,`Transfer failed: ${t.name||"file"}`);
  else if(t.status==="complete"&&t.direction==="download"&&shouldNotify("sent",t))toast(api,`Sent to phone / PC: ${t.name||"file"}`);
}
function withTimeout(promise,ms,label){
  return Promise.race([promise,new Promise((_,reject)=>setTimeout(()=>reject(new Error(`${label} timed out after ${Math.ceil(ms/1000)}s`)),ms))]);
}

function dirname(p){
  if(!p)return null;
  const i=p.lastIndexOf("/");
  return i>0?p.slice(0,i):"/";
}
function browseFileIcon(item){
  if(item&&item.type==="dir")return "📁";
  const name=String(item&&item.name||"").toLowerCase();
  if(/\.(jpg|jpeg|png|gif)$/.test(name))return "🖼️";
  if(/\.(mp4|mkv|mov|avi|webm|m4v)$/.test(name))return "🎬";
  if(/\.(zip|7z|rar)$/.test(name))return "🗜️";
  if(/\.iso$/.test(name))return "💿";
  if(/\.pdf$/.test(name))return "📕";
  if(/\.txt$/.test(name))return "📝";
  return "📄";
}
function browseDate(ts){
  const n=Number(ts||0);
  if(!Number.isFinite(n)||n<=0)return "";
  try{return new Date(n*1000).toISOString().slice(0,10);}catch(e){return "";}
}
function browseCrumbsFor(current,roots){
  if(!current)return [];
  const match=(roots||[]).filter(r=>current===r.path||current.startsWith(r.path+"/")).sort((a,b)=>b.path.length-a.path.length)[0];
  if(!match)return [{label:current,path:current}];
  const crumbs=[{label:match.name,path:match.path}];
  let acc=match.path;
  const rest=current.slice(match.path.length).split("/").filter(Boolean);
  for(const part of rest){acc=acc.replace(/\/$/,"")+"/"+part;crumbs.push({label:part,path:acc});}
  return crumbs;
}
function browseVisibleItems(items,query,sortMode){
  const q=String(query||"").trim().toLowerCase();
  const list=[];
  for(const it of (items||[])){
    const name=String(it&&it.name||"");
    const lower=name.toLowerCase();
    if(q&&!lower.includes(q))continue;
    list.push({it,lower,mtime:Number(it&&it.mtime)||0,size:Number(it&&it.size)||0});
  }
  list.sort((a,b)=>{
    if(a.it.type!==b.it.type)return a.it.type==="dir"?-1:1;
    if(sortMode==="date"&&a.mtime!==b.mtime)return b.mtime-a.mtime;
    if(sortMode==="size"&&a.size!==b.size)return b.size-a.size;
    if(a.lower<b.lower)return -1;
    if(a.lower>b.lower)return 1;
    return 0;
  });
  return list.map(x=>x.it);
}

function Bar({value}){return h("div",{style:{height:8,borderRadius:6,background:"rgba(255,255,255,.12)",overflow:"hidden",marginTop:7}},h("div",{style:{height:"100%",width:`${Math.max(0,Math.min(100,value||0))}%`,background:"#66c0f4"}}));}
function Btn({children,onClick,disabled=false}){return h(DialogButton,{disabled,onClick,style:{width:"100%",padding:"11px 12px",margin:"5px 0",borderRadius:11,border:"1px solid rgba(130,190,255,.20)",background:disabled?"rgba(255,255,255,.05)":"rgba(34,67,106,.72)",color:"white",fontSize:13,textAlign:"left"}},children);}
function Card({children,style={}}){return h("div",{style:{background:"linear-gradient(180deg,rgba(22,42,68,.92),rgba(15,29,49,.92))",border:"1px solid rgba(120,180,255,.16)",borderRadius:15,padding:13,margin:"10px 0",boxShadow:"0 5px 18px rgba(0,0,0,.12)",...style}},children);}
function SectionTitle({icon,title,sub}){return h("div",{style:{display:"flex",gap:9,alignItems:"center",marginBottom:9}},h("div",{style:{fontSize:21}},icon),h("div",{style:{minWidth:0}},h("div",{style:{fontWeight:760,fontSize:15}},title),sub&&h("div",{style:{fontSize:11,opacity:.62,marginTop:1,lineHeight:1.3}},sub)));}
function MiniButton({children,onClick,tone="normal"}){
  const danger=tone==="danger";
  return h(DialogButton,{onClick,style:{padding:"7px 9px",borderRadius:9,border:danger?"1px solid rgba(255,110,110,.34)":"1px solid rgba(120,180,255,.24)",background:danger?"rgba(255,70,70,.10)":"rgba(68,122,184,.13)",color:danger?"#ffd0d0":"#d9edff",fontSize:11,fontWeight:700}},children);
}

function DeckyShareBrandIcon({size=24}){
  return h("svg",{viewBox:"0 0 24 24",width:size,height:size,fill:"none",stroke:"currentColor",strokeWidth:2.05,strokeLinecap:"round",strokeLinejoin:"round","aria-hidden":"true",style:{display:"block",color:"currentColor",flexShrink:0}},
    h("rect",{x:"3.5",y:"5.5",width:"5",height:"13",rx:"1.4"}),
    h("rect",{x:"15.5",y:"5.5",width:"5",height:"13",rx:"1.4"}),
    h("path",{d:"M9.7 9h4.5"}),
    h("path",{d:"m12.6 7.4 1.6 1.6-1.6 1.6"}),
    h("path",{d:"M14.3 15H9.8"}),
    h("path",{d:"m11.4 13.4-1.6 1.6 1.6 1.6"}),
    h("path",{d:"M5.5 16.2h1"}),
    h("path",{d:"M17.5 16.2h1"})
  );
}

function connectDeckyBackend(){
  const init=window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
  if(!init||typeof init.connect!=="function")throw new Error("Decky loader API is not initialized");
  try{return init.connect(2,"DeckyShare");}catch(e){return init.connect(1,"DeckyShare");}
}

function deckyLoaderBackend(){
  const loader=window.DeckyBackend;
  if(!loader||typeof loader.call!=="function")throw new Error("Decky Loader install API is unavailable");
  return loader;
}

function makePanel(){
  let backendAPI=null;
  try{backendAPI=connectDeckyBackend();}catch(e){console.error("[DeckyShare] API connect failed",e);}
  return function Panel(){
    const [status,setStatus]=useState(null),[roots,setRoots]=useState([]),[path,setPath]=useState(null),[parent,setParent]=useState(null),[items,setItems]=useState([]),[err,setErr]=useState(""),[connIndex,setConnIndex]=useState(0),[deleteArmed,setDeleteArmed]=useState(null),[notifyOn,setNotifyOn]=useState(notificationsEnabled()),[copied,setCopied]=useState(false),[copiedPath,setCopiedPath]=useState(null),[updateInfo,setUpdateInfo]=useState(null),[updateBusy,setUpdateBusy]=useState(false),[updateArmed,setUpdateArmed]=useState(false),[rollbackArmed,setRollbackArmed]=useState(false),[shortcutPair,setShortcutPair]=useState(null),[shortcutPairBusy,setShortcutPairBusy]=useState(false),[browseQuery,setBrowseQuery]=useState(""),[browseSort,setBrowseSort]=useState("name"),[fmStorage,setFmStorage]=useState(null),[fmSelect,setFmSelect]=useState(false),[fmPicked,setFmPicked]=useState([]),[fmClip,setFmClip]=useState(null),[fmBusy,setFmBusy]=useState(false),[fmNew,setFmNew]=useState(""),[fmRename,setFmRename]=useState(null),[fmRenameValue,setFmRenameValue]=useState(""),[fmInfo,setFmInfo]=useState(null),[fmTrashArmed,setFmTrashArmed]=useState(false),[browseLimit,setBrowseLimit]=useState(50),[fmMenu,setFmMenu]=useState(false);
    const lastReceivedRef=useRef(null);
    const transferStatesRef=useRef(new Map());
    const firstBrowseItemRef=useRef(null);

    async function call(method,args={}){
      if(!backendAPI)backendAPI=connectDeckyBackend();
      if(!backendAPI||typeof backendAPI.call!=="function")throw new Error("Decky backend call API unavailable");
      const r=Object.keys(args).length?await backendAPI.call(method,args):await backendAPI.call(method);
      return r&&Object.prototype.hasOwnProperty.call(r,"result")?r.result:r;
    }
    function observeTransfers(transfers){
      const next=new Map();
      for(const t of transfers||[]){
        const prev=transferStatesRef.current.get(t.id);
        if(prev!==t.status&&(t.status==="failed"||(t.status==="complete"&&t.direction==="download")))showTransferResult(backendAPI,t);
        next.set(t.id,t.status);
      }
      transferStatesRef.current=next;
    }
    async function bootstrap(){
      try{
        setErr("");const b=await withTimeout(call("bootstrap"),6500,"Backend startup");if(!b||!b.ok)throw new Error("Backend returned invalid startup data");
        setStatus(b);setRoots(b.roots||[]);setConnIndex(0);
        if(b.received&&b.received.length)lastReceivedRef.current=b.received[0].path;
        transferStatesRef.current=new Map((b.transfers||[]).map(t=>[t.id,t.status]));
      }catch(e){setErr("Backend error: "+String(e&&e.message||e));}
    }
    async function refreshStatus(){
      try{
        const s=await call("status");
        if(s&&s.ok){
          const newest=s.received&&s.received.length?s.received[0]:null;
          if(newest&&lastReceivedRef.current&&newest.path!==lastReceivedRef.current)queueReceivedToast(backendAPI,newest);
          if(newest)lastReceivedRef.current=newest.path;
          observeTransfers(s.transfers||[]);
          setStatus(x=>({...x,...s}));
        }
      }catch(e){setErr("Status: "+String(e&&e.message||e));}
    }
    async function browse(p){try{const j=await call("browse",{path:p});setPath(j.path);setParent(j.parent);setItems(j.items||[]);setFmStorage(j.storage||null);setBrowseQuery("");setBrowseLimit(50);setFmPicked([]);setFmSelect(false);setFmInfo(null);setFmRename(null);setFmMenu(false);setErr("");}catch(e){setErr("Browse: "+String(e&&e.message||e));}}
    function leaveBrowser(){
      setPath(null);setParent(null);setItems([]);setBrowseQuery("");setBrowseLimit(50);
      setFmPicked([]);setFmSelect(false);setFmInfo(null);setFmRename(null);setFmMenu(false);
    }
    function navigateBack(){
      if(!path)return false;
      const atLocationRoot=(roots||[]).some(r=>r.path===path);
      if(atLocationRoot||!parent)leaveBrowser();
      else browse(parent);
      return true;
    }
    function consumeCancel(e){
      try{if(e&&typeof e.preventDefault==="function")e.preventDefault();}catch(_e){}
      try{if(e&&typeof e.stopPropagation==="function")e.stopPropagation();}catch(_e){}
    }
    function handleControllerBack(e){
      if(fmMenu){consumeCancel(e);setFmMenu(false);return;}
      if(fmNew){consumeCancel(e);setFmNew("");return;}
      if(fmRename){consumeCancel(e);setFmRename(null);setFmRenameValue("");return;}
      if(fmInfo){consumeCancel(e);setFmInfo(null);return;}
      if(fmSelect){consumeCancel(e);setFmSelect(false);setFmPicked([]);return;}
      if(status&&status.selected){consumeCancel(e);clearSelection();return;}
      if(path){consumeCancel(e);navigateBack();}
    }
    async function selectFile(p){try{await call("select_file",{path:p});await refreshStatus();}catch(e){setErr("Selection: "+String(e&&e.message||e));}}
    async function clearSelection(){try{await call("clear_selection");await refreshStatus();}catch(e){setErr("Clear selection: "+String(e&&e.message||e));}}
    async function showReceivedFolder(p){
      try{
        await call("clear_selection");
        setStatus(s=>({...s,selected:null}));
        await browse(dirname(p));
      }catch(e){setErr("Show folder: "+String(e&&e.message||e));}
    }
    async function copyText(text,label="Path"){
      if(!text)return false;
      const ok=await copyToClipboard(text);
      if(ok){
        setCopiedPath(text);
        setErr("");
        setTimeout(()=>setCopiedPath(p=>p===text?null:p),1600);
        return true;
      }
      setCopiedPath(null);
      setErr(`Copy ${label.toLowerCase()} failed — clipboard is blocked in this Decky view`);
      return false;
    }
    async function deleteReceived(p){
      if(deleteArmed!==p){setDeleteArmed(p);return;}
      try{setDeleteArmed(null);const r=await call("delete_received",{path:p});setStatus(s=>({...s,received:r&&r.received?r.received:(s.received||[]).filter(x=>x.path!==p)}));}
      catch(e){setDeleteArmed(null);setErr("Delete: "+String(e&&e.message||e));}
    }
    function fmToggle(it){setFmSelect(true);setFmInfo(null);setFmPicked(v=>v.includes(it.path)?v.filter(x=>x!==it.path):[...v,it.path]);}
    async function fmMkdir(){if(!path||!fmNew.trim()||fmBusy)return;setFmBusy(true);try{await call("file_mkdir",{parent:path,name:fmNew.trim()});setFmNew("");await browse(path);}catch(e){setErr("New folder: "+String(e&&e.message||e));}finally{setFmBusy(false);}}
    function fmStage(mode){if(fmPicked.length){setFmClip({mode,paths:fmPicked.slice()});setFmPicked([]);setFmSelect(false);}}
    async function fmPaste(){if(!fmClip||!path||fmBusy)return;const c=fmClip;setFmBusy(true);try{await call(c.mode==="move"?"file_move":"file_copy",{paths:c.paths,destination:path});setFmClip(null);await browse(path);}catch(e){setErr("Paste: "+String(e&&e.message||e));}finally{setFmBusy(false);}}
    async function fmDoRename(){if(!fmRename||!fmRenameValue.trim()||fmBusy)return;setFmBusy(true);try{await call("file_rename",{path:fmRename.path,name:fmRenameValue.trim()});setFmRename(null);setFmRenameValue("");await browse(path);}catch(e){setErr("Rename: "+String(e&&e.message||e));}finally{setFmBusy(false);}}
    async function fmDetails(it){try{const r=await call("file_details",{path:it.path});setFmInfo(r.item||null);}catch(e){setErr("Details: "+String(e&&e.message||e));}}
    async function fmTrash(){if(!fmPicked.length||fmBusy)return;if(!fmTrashArmed){setFmTrashArmed(true);setTimeout(()=>setFmTrashArmed(false),7000);return;}setFmBusy(true);try{await call("file_trash",{paths:fmPicked});setFmPicked([]);setFmSelect(false);setFmTrashArmed(false);await browse(path);await refreshStatus();}catch(e){setErr("Trash: "+String(e&&e.message||e));}finally{setFmBusy(false);}}

    async function copyToClipboard(text){
      if(!text)return false;
      let ok=false;
      try{
        if(navigator.clipboard&&typeof navigator.clipboard.writeText==="function"){
          try{await navigator.clipboard.writeText(text);ok=true;}catch(e){}
        }
        if(!ok&&typeof document!=="undefined"){
          const ta=document.createElement("textarea");
          ta.value=text;
          ta.setAttribute("readonly","");
          ta.style.position="fixed";
          ta.style.left="-9999px";
          ta.style.top="0";
          ta.style.opacity="0";
          document.body.appendChild(ta);
          ta.focus();
          ta.select();
          if(typeof ta.setSelectionRange==="function")ta.setSelectionRange(0,text.length);
          try{ok=!!document.execCommand("copy");}catch(e){ok=false;}
          document.body.removeChild(ta);
        }
      }catch(e){ok=false;}
      return ok;
    }
    async function copyAddress(){
      if(!displayUrl)return;
      const ok=await copyToClipboard(displayUrl);
      if(ok){
        setCopied(true);
        setErr("");
        setTimeout(()=>setCopied(false),1600);
      }else{
        setCopied(false);
        setErr("Copy address failed — clipboard is blocked in this Decky view");
      }
    }
    function toggleNotifications(){const next=!notifyOn;setNotifyOn(next);saveNotificationsEnabled(next);if(next)notifySeen.clear();else{receivedBatch=[];if(receivedBatchTimer){clearTimeout(receivedBatchTimer);receivedBatchTimer=null;}}}
    async function checkUpdate(force=false){
      if(updateBusy)return;
      setUpdateBusy(true);setUpdateArmed(false);setRollbackArmed(false);
      try{
        const r=await call("check_update",{force:!!force});
        setUpdateInfo(r||{ok:false,error:"No update response"});
        if(r&&!r.ok)setErr("Update: "+String(r.error||"check failed"));else if(err.startsWith("Update:"))setErr("");
      }catch(e){const msg=String(e&&e.message||e);setUpdateInfo({ok:false,error:msg});setErr("Update: "+msg);}
      finally{setUpdateBusy(false);}
    }
    async function installUpdate(){
      if(updateBusy||!updateInfo||!updateInfo.available)return;
      if(!updateArmed){setUpdateArmed(true);setTimeout(()=>setUpdateArmed(false),7000);return;}
      setUpdateBusy(true);setUpdateArmed(false);
      try{
        const r=await call("install_update",{tag:updateInfo.latest_tag});
        if(!r||!r.ok||!r.request_install)throw new Error(r&&r.error||"Update preparation failed");
        const loader=deckyLoaderBackend();
        await loader.call("utilities/install_plugin",r.artifact,r.name||"DeckyShare",r.version,r.sha256,Number(r.install_type||2));
        setUpdateInfo(x=>({...x,installer_prompted:true,prepared_version:r.version})); setErr(""); toast(backendAPI,`Decky confirmation opened for v${r.version}`);
      }catch(e){const msg=String(e&&e.message||e);setErr("Update: "+msg);setUpdateInfo(x=>({...x,install_error:msg}));}
      finally{setUpdateBusy(false);}
    }
    async function rollbackUpdate(){
      if(updateBusy||!updateInfo||!updateInfo.rollback_available)return;
      if(!rollbackArmed){setRollbackArmed(true);setTimeout(()=>setRollbackArmed(false),7000);return;}
      setUpdateBusy(true);setRollbackArmed(false);
      try{
        const r=await call("rollback_update");
        if(!r||!r.ok)throw new Error(r&&r.error||"Rollback failed");
        setUpdateInfo(x=>({...x,...r,installed_now:true,current:r.installed,rollback_available:false}));
        setErr("");toast(backendAPI,`Restored DeckyShare ${r.installed} • reload required`);
      }catch(e){const msg=String(e&&e.message||e);setErr("Rollback: "+msg);}
      finally{setUpdateBusy(false);}
    }

    async function startShortcutPairing(){
      if(shortcutPairBusy)return;
      setShortcutPairBusy(true);
      try{
        const r=await call("shortcut_pairing_start");
        if(!r||!r.ok)throw new Error(r&&r.error||"Could not start pairing");
        setShortcutPair(r);setErr("");
      }catch(e){setErr("iPhone pairing: "+String(e&&e.message||e));}
      finally{setShortcutPairBusy(false);}
    }

    useEffect(()=>{bootstrap();},[]);
    useEffect(()=>{if(!status)return;const t=setInterval(refreshStatus,path?4000:1500);return()=>clearInterval(t);},[!!status,!!path]);
    useEffect(()=>{if(!path||status&&status.selected)return;const t=setTimeout(()=>{try{if(firstBrowseItemRef.current&&typeof firstBrowseItemRef.current.focus==="function")firstBrowseItemRef.current.focus();}catch(e){}},80);return()=>clearTimeout(t);},[path,items,status&&status.selected]);

    const conns=status&&status.addresses||[];
    const activeConn=conns[Math.min(connIndex,Math.max(0,conns.length-1))]||null;
    const displayUrl=activeConn?activeConn.url:status&&status.address||"";
    const displayQr=activeConn?activeConn.qr_data:status&&status.qr_data||null;
    const browseCrumbs=path?browseCrumbsFor(path,roots):[];
    const visibleBrowseItems=useMemo(()=>path?browseVisibleItems(items,browseQuery,browseSort):[],[path,items,browseQuery,browseSort]);
    const fmChosen=useMemo(()=>items.filter(x=>fmPicked.includes(x.path)),[items,fmPicked]);
    const fmUsed=fmStorage&&fmStorage.total?(fmStorage.used*100/fmStorage.total):0;

    if(err&&!status)return h("div",{style:{padding:12}},err,h(Btn,{onClick:bootstrap},"Retry backend"));
    if(!status)return h("div",{style:{padding:12}},"Starting DeckyShare backend…");

    return h(Focusable,{onCancel:handleControllerBack,style:{padding:"4px 8px 18px",fontSize:14,color:"white"}},
      h("div",{style:{display:"flex",alignItems:"center",gap:10,padding:"8px 4px 12px"}},h(DeckyShareBrandIcon,{size:31}),h("div",{style:{flex:1}},h("div",{style:{display:"flex",gap:7,alignItems:"center"}},h("div",{style:{fontWeight:820,fontSize:20,letterSpacing:.1}},"DeckyShare"),h("span",{style:{fontSize:8,fontWeight:800,padding:"1px 5px",borderRadius:999,background:"rgba(80,160,255,.16)",border:"1px solid rgba(100,180,255,.24)",color:"#9fd4ff"}},"RC11.6")),h("div",{style:{fontSize:11,color:"#9fc7ff",opacity:.88}},"Share files with your Steam Deck"))),

      h(Card,{style:{border:"1px solid rgba(66,153,255,.28)"}},
        h(SectionTitle,{icon:"📡",title:"Connect phone / PC",sub:"Scan the QR code or open the local address"}),
        h("div",{style:{display:"inline-flex",alignItems:"center",gap:6,padding:"5px 8px",borderRadius:999,background:status.server_self_test?"rgba(56,232,121,.10)":"rgba(255,112,112,.10)",color:status.server_self_test?"#8ef6aa":"#ffb3b3",fontSize:11,fontWeight:700,marginBottom:10}},status.server_self_test?"● Ready to connect":"● Server unavailable"),
        h("div",{style:{display:"flex",gap:10,alignItems:"stretch"}},
          h("div",{style:{flex:1,minWidth:0,display:"flex",flexDirection:"column",gap:7}},
            h("div",{style:{padding:"10px 9px",borderRadius:10,background:"rgba(43,112,196,.20)",border:"1px solid rgba(79,164,255,.26)",fontSize:10,fontWeight:750,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",color:"#79cbff"}},displayUrl),
            h(MiniButton,{onClick:copyAddress},copied?"✓ Address copied":"Copy address")
          ),
          displayQr&&h("div",{style:{width:91,textAlign:"center"}},h("img",{src:displayQr,style:{width:80,height:80,background:"white",padding:4,borderRadius:9}}),h("div",{style:{fontSize:9,opacity:.55,marginTop:2}},"Scan QR"))
        ),
        conns.length>1&&h("div",{style:{marginTop:9}},h("div",{style:{fontSize:10,opacity:.52,marginBottom:4}},"Network"),conns.map((c,i)=>h(DialogButton,{key:c.ip,onClick:()=>{setConnIndex(i);setCopied(false);},style:{padding:"5px 7px",margin:"2px 3px 2px 0",borderRadius:7,border:i===connIndex?"1px solid #66c0f4":"1px solid rgba(255,255,255,.10)",background:i===connIndex?"rgba(102,192,244,.16)":"transparent",color:"white",fontSize:10}},c.interface)))
      ),

      h(Card,{style:{border:"1px solid rgba(120,180,255,.19)"}},
        h(SectionTitle,{icon:"📁",title:"Browse Files"}),
        !status.selected&&!path&&h("div",null,
          roots.map(r=>h(DialogButton,{key:r.path,onClick:()=>browse(r.path),style:{width:"100%",padding:"9px 10px",margin:"4px 0",borderRadius:11,border:"1px solid rgba(120,180,255,.12)",background:"rgba(20,39,63,.50)",color:"white",textAlign:"left"}},
            h("div",{style:{display:"flex",alignItems:"center",gap:9}},
              h("div",{style:{width:32,height:32,borderRadius:9,display:"flex",alignItems:"center",justifyContent:"center",background:"rgba(102,192,244,.10)",fontSize:16}},r.name.startsWith("Drive:")?"💾":"📂"),
              h("div",{style:{minWidth:0,flex:1,fontWeight:730,fontSize:11,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}},r.name),
              h("div",{style:{fontSize:15,opacity:.34}},"›")
            )
          ))
        ),
        status.selected?h("div",{style:{padding:10,borderRadius:11,background:"rgba(73,151,220,.10)",border:"1px solid rgba(100,175,240,.16)"}},
          h("div",{style:{display:"flex",gap:9,alignItems:"center"}},
            h("div",{style:{width:34,height:34,borderRadius:9,display:"flex",alignItems:"center",justifyContent:"center",background:"rgba(102,192,244,.10)",fontSize:18}},browseFileIcon(status.selected)),
            h("div",{style:{minWidth:0,flex:1}},h("div",{style:{fontWeight:750,wordBreak:"break-word"}},status.selected.name),h("div",{style:{fontSize:11,opacity:.6,marginTop:2}},status.selected.size_human))
          ),
          h(Btn,{onClick:clearSelection},"Choose another file")
        ):path&&h("div",null,

          fmNew&&h("div",{style:{display:"grid",gridTemplateColumns:"1fr auto",gap:6,marginBottom:7}},h(TextField,{value:fmNew==="New folder"?"":fmNew,onChange:e=>setFmNew(e.target.value),placeholder:"Folder name",style:{minWidth:0,padding:"8px",borderRadius:8,background:"#0c1a2b",color:"white",border:"1px solid rgba(120,180,255,.18)"}}),h(MiniButton,{onClick:fmMkdir},"Create")),
          fmClip&&h("div",{style:{padding:7,borderRadius:9,marginBottom:7,background:"rgba(255,190,75,.08)",border:"1px solid rgba(255,190,75,.20)"}},h("div",{style:{fontSize:10,marginBottom:5}},`${fmClip.mode==="move"?"Move":"Copy"} ${fmClip.paths.length} item(s) here?`),h("div",{style:{display:"flex",gap:5}},h(MiniButton,{onClick:fmPaste},"Paste here"),h(MiniButton,{onClick:()=>setFmClip(null)},"Cancel"))),
          fmRename&&h("div",{style:{display:"grid",gridTemplateColumns:"1fr auto",gap:6,marginBottom:7}},h(TextField,{value:fmRenameValue,onChange:e=>setFmRenameValue(e.target.value),style:{minWidth:0,padding:"8px",borderRadius:8,background:"#0c1a2b",color:"white",border:"1px solid rgba(120,180,255,.18)"}}),h(MiniButton,{onClick:fmDoRename},"Rename")),
          fmInfo&&h("div",{style:{padding:8,borderRadius:9,marginBottom:7,background:"rgba(255,255,255,.025)",border:"1px solid rgba(120,180,255,.12)",fontSize:9}},h("div",{style:{fontWeight:760,fontSize:11}},`${browseFileIcon(fmInfo)} ${fmInfo.name}`),h("div",{style:{opacity:.55,wordBreak:"break-all",marginTop:3}},fmInfo.path),h("div",{style:{opacity:.55,marginTop:2}},fmInfo.type==="dir"?`Folder${fmInfo.item_count!=null?` • ${fmInfo.item_count} item(s)`:""}`:`${fmInfo.size_human}${fmInfo.mime?` • ${fmInfo.mime}`:""}`)),
          h("div",{style:{display:"grid",gridTemplateColumns:"auto minmax(0,1fr) auto",gap:6,alignItems:"center",marginBottom:7}},
            h(DialogButton,{onClick:navigateBack,style:{width:38,height:34,minWidth:38,padding:0,margin:0,borderRadius:9,border:"1px solid rgba(120,180,255,.16)",background:"rgba(255,255,255,.025)",color:"#d9edff",fontSize:18,fontWeight:800}},"←"),
            h("div",{style:{display:"flex",gap:3,alignItems:"center",minWidth:0,overflow:"hidden",padding:"6px 7px",borderRadius:9,background:"rgba(7,17,29,.34)",border:"1px solid rgba(120,180,255,.10)"}},
              browseCrumbs.map((c,i)=>h(React.Fragment,{key:c.path},
                i>0&&h("span",{style:{fontSize:9,opacity:.30}},"›"),
                h(DialogButton,{onClick:()=>c.path===path?null:browse(c.path),disabled:c.path===path,style:{padding:"2px 3px",border:0,background:"transparent",color:c.path===path?"#fff":"#8fd3ff",fontSize:9,fontWeight:c.path===path?760:620,maxWidth:96,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",flexShrink:i===browseCrumbs.length-1?1:0}},c.label)
              ))
            ),
            h(DialogButton,{onClick:()=>setFmMenu(v=>!v),style:{width:38,height:34,borderRadius:9,border:fmMenu?"1px solid #66c0f4":"1px solid rgba(120,180,255,.16)",background:fmMenu?"rgba(102,192,244,.14)":"rgba(255,255,255,.025)",color:"#d9edff",fontSize:18,fontWeight:800}},"⋯")
          ),
          fmMenu&&h("div",{style:{padding:8,marginBottom:7,borderRadius:10,background:"rgba(9,22,38,.92)",border:"1px solid rgba(120,180,255,.16)"}},
            h("div",{style:{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:5,marginBottom:fmStorage||roots.length?7:0}},
              h(MiniButton,{onClick:()=>{setPath(null);setParent(null);setItems([]);setBrowseQuery("");setFmMenu(false);}},"Locations"),
              h(MiniButton,{onClick:()=>{setFmSelect(v=>!v);setFmPicked([]);setFmInfo(null);setFmMenu(false);}},fmSelect?"Done":"Select"),
              h(MiniButton,{onClick:()=>{setFmNew(fmNew?"":"New folder");setFmMenu(false);}},fmNew?"Cancel":"New folder")
            ),
            fmStorage&&h("div",{style:{fontSize:9,opacity:.55,marginBottom:7}},`${fmStorage.used_human} used • ${fmStorage.free_human} free`,h(Bar,{value:fmUsed})),
            roots.length>0&&h("div",{style:{display:"flex",gap:4,overflowX:"auto",paddingBottom:2}},roots.map(r=>h(DialogButton,{key:r.path,onClick:()=>{setFmMenu(false);browse(r.path);},style:{flex:"0 0 auto",padding:"5px 7px",borderRadius:999,border:path===r.path?"1px solid #66c0f4":"1px solid rgba(120,180,255,.14)",background:path===r.path?"rgba(102,192,244,.13)":"rgba(255,255,255,.025)",color:path===r.path?"#a9ddff":"#d9edff",fontSize:9,fontWeight:700}},r.name.startsWith("Drive:")?`💾 ${r.name.replace("Drive: ","")}`:r.name)))
          ),
          h("div",{style:{display:"grid",gridTemplateColumns:"1fr auto",gap:6,marginBottom:6}},
            h(TextField,{value:browseQuery,onChange:e=>{setBrowseQuery(e.target.value);setBrowseLimit(50);},placeholder:"Search files",style:{minWidth:0,width:"100%",boxSizing:"border-box",padding:"9px 10px",borderRadius:10,border:"1px solid rgba(120,180,255,.18)",background:"rgba(7,17,29,.48)",color:"white",fontSize:11,outline:"none"}}),
            h(DialogButton,{onClick:()=>{const next=browseSort==="name"?"date":browseSort==="date"?"size":"name";setBrowseSort(next);setBrowseLimit(50);},style:{minWidth:82,padding:"7px 8px",borderRadius:10,border:"1px solid rgba(120,180,255,.16)",background:"rgba(255,255,255,.025)",color:"#d9edff",fontSize:9,fontWeight:720,whiteSpace:"nowrap"}},`Sort: ${browseSort==="date"?"Newest":browseSort==="size"?"Largest":"Name"}`)
          ),
          h("div",{style:{fontSize:9,opacity:.42,margin:"4px 1px 7px"}},`${visibleBrowseItems.length} item${visibleBrowseItems.length===1?"":"s"}${browseQuery?` matching “${browseQuery}”`:""}`),
          !visibleBrowseItems.length?h("div",{style:{padding:"15px 8px",textAlign:"center",fontSize:11,opacity:.5,border:"1px dashed rgba(120,180,255,.14)",borderRadius:10}},browseQuery?"No matching items in this folder":"This folder is empty"):visibleBrowseItems.slice(0,browseLimit).map((it,index)=>h(DialogButton,{key:it.path,ref:index===0?firstBrowseItemRef:null,onClick:()=>fmSelect?fmToggle(it):(it.type==="dir"?browse(it.path):selectFile(it.path)),onFocus:e=>{e.currentTarget.style.borderColor="#66c0f4";e.currentTarget.style.background="rgba(35,72,108,.68)";},onBlur:e=>{const picked=fmPicked.includes(it.path);e.currentTarget.style.borderColor=picked?"#66c0f4":"rgba(120,180,255,.11)";e.currentTarget.style.background=picked?"rgba(48,92,132,.68)":"rgba(20,39,63,.46)";},style:{width:"100%",padding:"5px 7px",margin:"2px 0",borderRadius:9,border:fmPicked.includes(it.path)?"1px solid #66c0f4":"1px solid rgba(120,180,255,.11)",background:fmPicked.includes(it.path)?"rgba(48,92,132,.68)":"rgba(20,39,63,.46)",boxShadow:fmPicked.includes(it.path)?"inset 3px 0 0 #66c0f4":"none",color:"white",textAlign:"left",transition:"background .12s ease,border-color .12s ease"}},
            h("div",{style:{display:"grid",gridTemplateColumns:"26px minmax(0,1fr) 18px",gap:7,alignItems:"center"}},
              h("div",{style:{width:26,height:26,borderRadius:7,display:"flex",alignItems:"center",justifyContent:"center",background:it.type==="dir"?"rgba(102,192,244,.09)":"rgba(255,255,255,.04)",fontSize:14,flexShrink:0}},browseFileIcon(it)),
              h("div",{style:{minWidth:0}},
                h("div",{style:{fontWeight:720,fontSize:10,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}},it.name),
                h("div",{style:{fontSize:9,opacity:.46,marginTop:1,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}},browseDate(it.mtime)||(it.type==="dir"?"Folder":""))
              ),
              h("div",{style:{fontSize:14,lineHeight:1,textAlign:"center",fontWeight:850,color:fmSelect&&fmPicked.includes(it.path)?"#9edcff":"#70869a",opacity:fmSelect||it.type==="dir"?1:.35}},fmSelect?(fmPicked.includes(it.path)?"✓":"○"):(it.type==="dir"?"›":""))
            )
          )),
          visibleBrowseItems.length>browseLimit&&h(DialogButton,{onClick:()=>setBrowseLimit(x=>Math.min(x+50,visibleBrowseItems.length)),style:{width:"100%",padding:"8px",marginTop:6,borderRadius:9,border:"1px solid rgba(120,180,255,.16)",background:"rgba(255,255,255,.025)",color:"#bde7ff",fontSize:10,fontWeight:700}},`Show 50 more • ${browseLimit} of ${visibleBrowseItems.length}`),
          fmSelect&&fmChosen.length>0&&h("div",{style:{position:"sticky",bottom:4,zIndex:3,padding:8,marginTop:8,borderRadius:10,background:"rgba(9,22,38,.97)",border:"1px solid rgba(102,192,244,.28)"}},h("div",{style:{fontSize:10,fontWeight:760,marginBottom:5}},`${fmChosen.length} selected`),h("div",{style:{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:5}},h(MiniButton,{onClick:()=>fmStage("copy")},"Copy"),h(MiniButton,{onClick:()=>fmStage("move")},"Move"),h(MiniButton,{onClick:()=>{if(fmChosen.length===1){setFmRename(fmChosen[0]);setFmRenameValue(fmChosen[0].name);}else setErr("Rename: select one item");}},"Rename"),h(MiniButton,{onClick:()=>fmChosen.length===1?fmDetails(fmChosen[0]):setErr("Details: select one item")},"Details"),h(MiniButton,{onClick:()=>{if(fmChosen.length===1&&fmChosen[0].type==="file")selectFile(fmChosen[0].path);else setErr("Share: select one file");}},"Share"),h(MiniButton,{onClick:fmTrash,tone:"danger"},fmTrashArmed?"Tap again":"Trash")))
        )
      ),

      h(Card,null,
        h(SectionTitle,{icon:"📥",title:"Received Files",sub:"Recent files sent from phone / PC"}),
        (!status.received||!status.received.length)?h("div",{style:{opacity:.5,fontSize:12,padding:"4px 0"}},"No received files yet"):status.received.map(f=>h("div",{key:f.path,style:{background:"rgba(28,54,87,.62)",border:"1px solid rgba(120,180,255,.12)",borderRadius:12,padding:10,margin:"7px 0"}},
          h("div",{style:{display:"flex",gap:9,alignItems:"center"}},h("div",{style:{width:34,height:34,borderRadius:9,display:"flex",alignItems:"center",justifyContent:"center",background:"rgba(120,77,255,.16)",fontSize:19}},"📦"),h("div",{style:{minWidth:0,flex:1}},h("div",{style:{fontWeight:740,wordBreak:"break-word"}},f.name),h("div",{style:{fontSize:10,opacity:.54,marginTop:2}},f.size_human))),
          h("div",{style:{fontSize:9,opacity:.42,marginTop:6,wordBreak:"break-all"}},f.path),
          h("div",{style:{display:"flex",gap:6,marginTop:8,flexWrap:"wrap"}},h(MiniButton,{onClick:()=>showReceivedFolder(f.path)},"Show folder"),h(MiniButton,{onClick:()=>copyText(f.path,"Path")},copiedPath===f.path?"✓ Copied":"Copy path"),h(MiniButton,{onClick:()=>deleteReceived(f.path),tone:"danger"},deleteArmed===f.path?"Tap again":"Delete"))
        ))
      ),

      h(Card,null,
        h(SectionTitle,{icon:"↔️",title:"Live Transfers",sub:"Progress, speed and ETA"}),
        (!status.transfers||!status.transfers.length)?h("div",{style:{opacity:.5,fontSize:12,padding:"4px 0"}},"No active transfers"):status.transfers.map(t=>h("div",{key:t.id,style:{padding:"8px 0",borderBottom:"1px solid rgba(255,255,255,.05)"}},h("div",{style:{fontWeight:680,wordBreak:"break-word"}},`${t.direction==="upload"?"Phone/PC → Deck":"Deck → Phone/PC"}  •  ${t.name}`),h("div",{style:{fontSize:11,opacity:.62,marginTop:2}},`${Number(t.percent||0).toFixed(1)}% • ${fmt(t.speed)}/s${t.eta?` • ETA ${Math.ceil(t.eta)}s`:""}`),h(Bar,{value:t.percent})))
      ),

      h(Card,{style:{border:"1px solid rgba(120,180,255,.18)"}},h(SectionTitle,{icon:"🔔",title:"Notifications",sub:"Received files, failed transfers and completed sends"}),h("div",{style:{display:"flex",alignItems:"center",justifyContent:"space-between",gap:10}},h("div",{style:{fontSize:11,opacity:.65,lineHeight:1.35}},notifyOn?"On • multi-file receives are grouped":"Notifications are off"),h(MiniButton,{onClick:toggleNotifications},notifyOn?"Turn off":"Turn on"))),
      h(Card,{style:{border:"1px solid rgba(96,211,152,.22)"}},
        h(SectionTitle,{icon:"⬆️",title:"Updates",sub:"Verified GitHub releases • manual install only"}),
        h("div",{style:{fontSize:11,opacity:.68,lineHeight:1.45,marginBottom:8}},updateInfo&&updateInfo.current?`Installed: v${updateInfo.current}`:"Installed: v1.1.0-rc.1"),
        updateInfo&&updateInfo.installed_now&&h("div",{style:{padding:"9px",borderRadius:10,background:"rgba(70,210,125,.10)",border:"1px solid rgba(80,220,140,.18)",fontSize:11,lineHeight:1.45,marginBottom:8}},`✓ ${updateInfo.installed} installed safely. Reload DeckyShare from Decky settings to finish.`),
        updateInfo&&updateInfo.ok&&updateInfo.latest&&updateInfo.available&&h("div",{style:{padding:"9px",borderRadius:10,background:"rgba(71,142,230,.10)",border:"1px solid rgba(100,180,255,.18)",marginBottom:8}},h("div",{style:{fontWeight:760,fontSize:12}},`v${updateInfo.latest} available`),h("div",{style:{fontSize:10,opacity:.6,marginTop:3}},`${fmt(updateInfo.asset_size||0)} • SHA-256 verified by GitHub`),updateInfo.notes&&h("div",{style:{fontSize:10,opacity:.68,whiteSpace:"pre-wrap",maxHeight:72,overflow:"hidden",marginTop:6}},updateInfo.notes)),
        updateInfo&&updateInfo.ok&&updateInfo.latest&&updateInfo.same&&h("div",{style:{fontSize:11,opacity:.68,marginBottom:8}},`✓ You're on the latest stable release (v${updateInfo.latest}).`),
        updateInfo&&updateInfo.ok&&updateInfo.latest&&updateInfo.ahead&&h("div",{style:{fontSize:11,opacity:.68,marginBottom:8}},`Development build detected. Latest stable release is v${updateInfo.latest}.`),
        updateInfo&&!updateInfo.ok&&updateInfo.error&&h("div",{style:{fontSize:11,color:"#ffb3b3",marginBottom:8,wordBreak:"break-word"}},updateInfo.error),
        h("div",{style:{display:"flex",gap:6,flexWrap:"wrap"}},
          h(MiniButton,{onClick:()=>checkUpdate(true)},updateBusy?"Working…":"Check for update"),
          updateInfo&&updateInfo.available&&h(MiniButton,{onClick:installUpdate},updateBusy?"Installing…":updateArmed?`Confirm v${updateInfo.latest}`:`Install v${updateInfo.latest}`),
          updateInfo&&updateInfo.rollback_available&&h(MiniButton,{onClick:rollbackUpdate,tone:"danger"},rollbackArmed?"Confirm rollback":"Rollback")
        ),
        h("div",{style:{fontSize:9,opacity:.42,lineHeight:1.35,marginTop:8}},"Updates use Decky Loader’s native installer. GitHub SHA-256 is verified and Decky asks before replacing the plugin.")
      ),
      h(Card,{style:{border:"1px solid rgba(255,190,75,.18)"}},h(SectionTitle,{icon:"☕",title:"Support DeckyShare",sub:"Free & open-source community project"}),h(DialogButton,{onClick:()=>{try{window.open("https://buymeacoffee.com/Gillrv","_blank");}catch(e){}},style:{width:"100%",padding:"10px 12px",borderRadius:10,border:"1px solid rgba(255,196,92,.30)",background:"rgba(255,183,65,.10)",color:"#ffe0a3",fontWeight:750}},"☕ Buy me a coffee")),
      err&&h("div",{style:{color:"#ffb3b3",marginTop:8,fontSize:11,wordBreak:"break-word"}},err)
    );
  };
}

export default function(){
  const Panel=makePanel();
  let notifyAPI=null,receiveListener=null;
  try{
    notifyAPI=connectDeckyBackend();
    if(notifyAPI&&typeof notifyAPI.addEventListener==="function"){
      receiveListener=(...args)=>queueReceivedToast(notifyAPI,args.length?args[args.length-1]:null);
      notifyAPI.addEventListener("file_received",receiveListener);
    }
  }catch(e){console.error("[DeckyShare] global receive notifications unavailable",e);}
  return {
    name:"DeckyShare",
    titleView:h("div",{style:{fontWeight:700}},"DeckyShare"),
    content:h(Panel),
    icon:h(DeckyShareBrandIcon,{size:22}),
    onDismount(){
      try{if(notifyAPI&&receiveListener&&typeof notifyAPI.removeEventListener==="function")notifyAPI.removeEventListener("file_received",receiveListener);}catch(e){}
      if(receivedBatchTimer){clearTimeout(receivedBatchTimer);receivedBatchTimer=null;}
      receivedBatch=[];
      console.log("DeckyShare UI unloaded");
    }
  };
}
