const React = window.SP_REACT || window.React;
const h = React.createElement;
const { useEffect, useRef, useState } = React;

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

function Bar({value}){return h("div",{style:{height:8,borderRadius:6,background:"rgba(255,255,255,.15)",overflow:"hidden",marginTop:6}},h("div",{style:{height:"100%",width:`${Math.max(0,Math.min(100,value||0))}%`,background:"#66c0f4"}}));}
function Btn({children,onClick,disabled=false}){return h("button",{disabled,onClick,style:{width:"100%",padding:"12px 13px",margin:"5px 0",borderRadius:12,border:"1px solid rgba(130,190,255,.22)",background:disabled?"rgba(255,255,255,.05)":"linear-gradient(180deg,rgba(44,79,120,.55),rgba(25,48,78,.55))",color:"white",fontSize:14,textAlign:"left"}},children);}
function Card({children,style={}}){return h("div",{style:{background:"linear-gradient(180deg,rgba(22,42,68,.88),rgba(15,29,49,.88))",border:"1px solid rgba(120,180,255,.18)",borderRadius:14,padding:12,margin:"9px 0",...style}},children);}
function SectionTitle({icon,title,sub}){return h("div",{style:{display:"flex",gap:9,alignItems:"center",marginBottom:8}},h("div",{style:{fontSize:22}},icon),h("div",null,h("div",{style:{fontWeight:750,fontSize:16}},title),sub&&h("div",{style:{fontSize:11,opacity:.65,marginTop:1}},sub)));}

function connectDeckyBackend(){
  const init=window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
  if(!init||typeof init.connect!=="function")throw new Error("Decky loader API is not initialized");
  try{return init.connect(2,"DeckyShare");}catch(e){return init.connect(1,"DeckyShare");}
}

function makePanel(){
  let backendAPI=null;
  try{backendAPI=connectDeckyBackend();}catch(e){console.error("[DeckyShare] API connect failed",e);}
  return function Panel(){
    const [status,setStatus]=useState(null),[roots,setRoots]=useState([]),[path,setPath]=useState(null),[parent,setParent]=useState(null),[items,setItems]=useState([]),[err,setErr]=useState(""),[connIndex,setConnIndex]=useState(0),[deleteArmed,setDeleteArmed]=useState(null),[notifyOn,setNotifyOn]=useState(notificationsEnabled());
    const lastReceivedRef=useRef(null);
    const transferStatesRef=useRef(new Map());

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
        setErr("");const b=await call("bootstrap");if(!b||!b.ok)throw new Error("Backend returned invalid startup data");
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
    async function browse(p){try{const j=await call("browse",{path:p});setPath(j.path);setParent(j.parent);setItems(j.items||[]);setErr("");}catch(e){setErr("Browse: "+String(e&&e.message||e));}}
    async function selectFile(p){try{await call("select_file",{path:p});await refreshStatus();}catch(e){setErr("Selection: "+String(e&&e.message||e));}}
    async function clearSelection(){try{await call("clear_selection");await refreshStatus();}catch(e){setErr("Clear selection: "+String(e&&e.message||e));}}
    async function deleteReceived(p){
      if(deleteArmed!==p){setDeleteArmed(p);return;}
      try{setDeleteArmed(null);const r=await call("delete_received",{path:p});setStatus(s=>({...s,received:r&&r.received?r.received:(s.received||[]).filter(x=>x.path!==p)}));}
      catch(e){setDeleteArmed(null);setErr("Delete: "+String(e&&e.message||e));}
    }
    function toggleNotifications(){const next=!notifyOn;setNotifyOn(next);saveNotificationsEnabled(next);if(next)notifySeen.clear();else{receivedBatch=[];if(receivedBatchTimer){clearTimeout(receivedBatchTimer);receivedBatchTimer=null;}}}

    useEffect(()=>{bootstrap();},[]);
    useEffect(()=>{if(!status)return;const t=setInterval(refreshStatus,1000);return()=>clearInterval(t);},[!!status]);

    const conns=status&&status.addresses||[];
    const activeConn=conns[Math.min(connIndex,Math.max(0,conns.length-1))]||null;
    const displayUrl=activeConn?activeConn.url:status&&status.address||"";
    const displayQr=activeConn?activeConn.qr_data:status&&status.qr_data||null;

    if(err&&!status)return h("div",{style:{padding:12}},err,h(Btn,{onClick:bootstrap},"Retry backend"));
    if(!status)return h("div",{style:{padding:12}},"Starting DeckyShare backend…");

    return h("div",{style:{padding:"4px 8px 16px",fontSize:14,color:"white"}},
      h("div",{style:{display:"flex",alignItems:"center",gap:10,padding:"8px 4px 11px"}},h("div",{style:{fontSize:30}},"◉"),h("div",{style:{flex:1}},h("div",{style:{display:"flex",gap:7,alignItems:"center"}},h("div",{style:{fontWeight:800,fontSize:20}},"DeckyShare"),h("span",{style:{fontSize:9,fontWeight:800,padding:"2px 6px",borderRadius:999,background:"rgba(80,160,255,.18)",color:"#9fd4ff"}},"v1.1-dev")),h("div",{style:{fontSize:11,color:"#9fc7ff"}},"Share files with your Steam Deck. Simple. Wireless. Fast."))),
      h(Card,null,h(SectionTitle,{icon:"📡",title:"Connect phone / PC",sub:"Open this address on your phone or computer"}),h("div",{style:{fontSize:12,color:status.server_self_test?"#7ef29a":"#ffb3b3",marginBottom:8}},status.server_self_test?`● Server OK • ${status.listen}`:"● Server self-test failed"),h("div",{style:{display:"flex",gap:10,alignItems:"center"}},h("div",{style:{flex:1,minWidth:0,padding:9,borderRadius:10,background:"rgba(43,112,196,.25)",fontSize:10,fontWeight:700,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",color:"#69c6ff"}},displayUrl),displayQr&&h("img",{src:displayQr,style:{width:80,height:80,background:"white",padding:4,borderRadius:9}})),conns.length>1&&h("div",{style:{marginTop:7}},conns.map((c,i)=>h("button",{key:c.ip,onClick:()=>setConnIndex(i),style:{padding:"5px 7px",margin:2,borderRadius:7,border:i===connIndex?"1px solid #66c0f4":"1px solid rgba(255,255,255,.12)",background:i===connIndex?"rgba(102,192,244,.18)":"transparent",color:"white",fontSize:11}},c.interface)))),
      h(Card,null,h(SectionTitle,{icon:"📁",title:"Browse Files",sub:"Tap a folder to open it"}),!status.selected&&!path&&h("div",{style:{display:"grid",gridTemplateColumns:"1fr 1fr",gap:7}},roots.map(r=>h("button",{key:r.path,onClick:()=>browse(r.path),style:{minHeight:64,padding:11,borderRadius:12,border:"1px solid rgba(104,170,255,.30)",background:"rgba(35,77,128,.68)",color:"white",fontWeight:700,textAlign:"left"}},`${r.name.startsWith("Drive:")?"💾":"📂"} ${r.name} ›`))),status.selected?h("div",null,h("div",{style:{fontWeight:700}},"✓ "+status.selected.name),h("div",{style:{fontSize:11,opacity:.65}},status.selected.size_human),h(Btn,{onClick:clearSelection},"Choose another file")):path&&h("div",null,h("div",{style:{display:"flex",gap:6}},h("button",{onClick:()=>{setPath(null);setParent(null);setItems([]);},style:{flex:1,padding:8,borderRadius:9,border:"1px solid rgba(102,192,244,.35)",background:"rgba(102,192,244,.12)",color:"white"}},"← Locations"),parent&&h("button",{onClick:()=>browse(parent),style:{flex:1,padding:8,borderRadius:9,border:"1px solid rgba(255,255,255,.14)",background:"transparent",color:"white"}},"↑ Up")),h("div",{style:{fontSize:10,opacity:.55,margin:"7px 1px",wordBreak:"break-all"}},path),items.slice(0,100).map(it=>h(Btn,{key:it.path,onClick:()=>it.type==="dir"?browse(it.path):selectFile(it.path)},it.type==="dir"?`📁 ${it.name} ›`:`📄 ${it.name} • ${it.size_human}`)))),
      h(Card,null,h(SectionTitle,{icon:"📥",title:"Received Files",sub:"Files received from phone / PC"}),(!status.received||!status.received.length)?h("div",{style:{opacity:.55,fontSize:12}},"No received files yet"):status.received.map(f=>h("div",{key:f.path,style:{background:"rgba(28,54,87,.72)",borderRadius:11,padding:10,margin:"7px 0"}},h("div",{style:{fontWeight:700}},f.name),h("div",{style:{fontSize:10,opacity:.6,wordBreak:"break-all"}},f.size_human+" • "+f.path),h("button",{onClick:()=>deleteReceived(f.path),style:{marginTop:7,padding:"6px 9px",borderRadius:8,border:"1px solid rgba(255,110,110,.38)",background:deleteArmed===f.path?"rgba(255,70,70,.28)":"rgba(255,70,70,.10)",color:"#ffd0d0"}},deleteArmed===f.path?"Tap again to delete":"Delete")))),
      h(Card,null,h(SectionTitle,{icon:"↔️",title:"Live Transfers",sub:"Speed and progress"}),(!status.transfers||!status.transfers.length)?h("div",{style:{opacity:.55,fontSize:12}},"No active transfers"):status.transfers.map(t=>h("div",{key:t.id,style:{padding:"7px 0"}},h("div",{style:{fontWeight:650}},`${t.direction==="upload"?"Phone/PC → Deck":"Deck → Phone/PC"}: ${t.name}`),h("div",{style:{fontSize:11,opacity:.65}},`${Number(t.percent||0).toFixed(1)}% • ${fmt(t.speed)}/s${t.eta?` • ETA ${Math.ceil(t.eta)}s`:""}`),h(Bar,{value:t.percent})))),
      h(Card,{style:{border:"1px solid rgba(120,180,255,.22)"}},h(SectionTitle,{icon:"🔔",title:"Notifications",sub:"Received files, failed transfers and completed sends"}),h("div",{style:{display:"flex",alignItems:"center",justifyContent:"space-between",gap:10}},h("div",{style:{fontSize:12,opacity:.72}},notifyOn?"On • multi-file receives are grouped":"Off"),h("button",{onClick:toggleNotifications,style:{padding:"8px 11px",borderRadius:9,border:"1px solid rgba(102,192,244,.35)",background:notifyOn?"rgba(102,192,244,.18)":"rgba(255,255,255,.06)",color:"white",fontWeight:700}},notifyOn?"Turn off":"Turn on"))),
      h(Card,{style:{border:"1px solid rgba(255,190,75,.22)"}},h(SectionTitle,{icon:"☕",title:"Support DeckyShare",sub:"Free & open-source community project"}),h("button",{onClick:()=>{try{window.open("https://buymeacoffee.com/Gillrv","_blank");}catch(e){}},style:{width:"100%",padding:"10px 12px",borderRadius:10,border:"1px solid rgba(255,196,92,.38)",background:"rgba(255,183,65,.13)",color:"#ffe0a3",fontWeight:750}},"☕ Buy me a coffee")),
      err&&h("div",{style:{color:"#ffb3b3",marginTop:8}},err)
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
    icon:h("div",{style:{fontSize:20}},"↔"),
    onDismount(){
      try{if(notifyAPI&&receiveListener&&typeof notifyAPI.removeEventListener==="function")notifyAPI.removeEventListener("file_received",receiveListener);}catch(e){}
      if(receivedBatchTimer){clearTimeout(receivedBatchTimer);receivedBatchTimer=null;}
      receivedBatch=[];
      console.log("DeckyShare UI unloaded");
    }
  };
}
