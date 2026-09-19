const React = window.SP_REACT || window.React;
const h = React.createElement;
const { useEffect, useMemo, useRef, useState } = React;

function fmt(n){
  if(!Number.isFinite(n)) return "0 B";
  if(n>=1073741824) return (n/1073741824).toFixed(1)+" GB";
  if(n>=1048576) return (n/1048576).toFixed(1)+" MB";
  if(n>=1024) return (n/1024).toFixed(1)+" KB";
  return Math.round(n)+" B";
}
function Bar({value}){return h("div",{style:{height:8,borderRadius:6,background:"rgba(255,255,255,.15)",overflow:"hidden",marginTop:6}},h("div",{style:{height:"100%",width:`${Math.max(0,Math.min(100,value||0))}%`,background:"#66c0f4"}}));}
function Btn({children,onClick,disabled=false}){return h("button",{disabled,onClick,style:{width:"100%",padding:"12px 13px",margin:"5px 0",borderRadius:12,border:"1px solid rgba(130,190,255,.22)",background:disabled?"rgba(255,255,255,.05)":"linear-gradient(180deg,rgba(44,79,120,.55),rgba(25,48,78,.55))",color:"white",fontSize:14,textAlign:"left",boxShadow:"inset 0 1px 0 rgba(255,255,255,.05)"}},children);}
function Card({children,style={}}){return h("div",{style:{background:"linear-gradient(180deg,rgba(22,42,68,.88),rgba(15,29,49,.88))",border:"1px solid rgba(120,180,255,.18)",borderRadius:14,padding:12,margin:"9px 0",...style}},children);}
function SectionTitle({icon,title,sub}){return h("div",{style:{display:"flex",gap:9,alignItems:"center",marginBottom:8}},h("div",{style:{fontSize:22}},icon),h("div",null,h("div",{style:{fontWeight:750,fontSize:16}},title),sub&&h("div",{style:{fontSize:11,opacity:.65,marginTop:1}},sub)));}


function connectDeckyBackend(){
  const init = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
  if(!init || typeof init.connect !== "function") throw new Error("Decky loader API is not initialized");
  try { return init.connect(2, "DeckyShareRemoteDemo"); }
  catch(e) { return init.connect(1, "DeckyShareRemoteDemo"); }
}

function showReceivedToast(api,item){
  if(!item) return;
  try{
    const payload=item.result||item.data||item;
    if(api && api.toaster && typeof api.toaster.toast==="function"){
      api.toaster.toast({
        title:"DeckyShare",
        body:`Received: ${payload.name || "file"}\nSaved to: ${payload.path || "Downloads/DeckShare"}`
      });
    }
  }catch(e){ console.error("[DeckShare] notification failed",e); }
}

function makePanel(){
  let backendAPI = null;
  try { backendAPI = connectDeckyBackend(); } catch(e) { console.error("[DeckShare] API connect failed", e); }
  return function Panel(){
    const [status,setStatus]=useState(null),[roots,setRoots]=useState([]),[path,setPath]=useState(null),[parent,setParent]=useState(null),[items,setItems]=useState([]),[err,setErr]=useState(""),[connIndex,setConnIndex]=useState(0),[deleteArmed,setDeleteArmed]=useState(null);
    const [remoteEmail,setRemoteEmail]=useState(""),[remoteState,setRemoteState]=useState("idle"),[remoteProgress,setRemoteProgress]=useState(0);
    const remoteTimerRef=useRef({resolve:null,interval:null});
    const lastReceivedRef=useRef(null);

    async function deckyCall(method,args={}){
      if(!backendAPI) backendAPI = connectDeckyBackend();
      if(!backendAPI || typeof backendAPI.call !== "function") throw new Error("Decky backend call API unavailable");
      const hasArgs = args && Object.keys(args).length > 0;
      const r = hasArgs ? await backendAPI.call(method,args) : await backendAPI.call(method);
      return r && Object.prototype.hasOwnProperty.call(r,"result") ? r.result : r;
    }

    async function browse(p){
      try{
        const j=await deckyCall("browse",{path:p});
        setPath(j.path);setParent(j.parent);setItems(j.items||[]);setErr("");
      }catch(e){setErr("Browse: "+String(e.message||e));}
    }

    async function bootstrap(){
      try{
        setErr("");
        const b=await deckyCall("bootstrap");
        if(!b || !b.ok) throw new Error("Backend returned invalid startup data");
        setStatus(b);setRoots(b.roots||[]);setConnIndex(0);
        if(b.received&&b.received.length) lastReceivedRef.current=b.received[0].path;
        // Keep file browser collapsed on startup. A root opens only after the user taps it.
      }catch(e){
        console.error("[DeckShare] bootstrap failed",e);
        setErr("Backend error: "+String((e&&e.message)||e));
      }
    }

    async function refreshStatus(){
      try{
        const s=await deckyCall("status");
        if(s&&s.ok){
          const newest=s.received&&s.received.length?s.received[0]:null;
          if(newest && lastReceivedRef.current && newest.path!==lastReceivedRef.current){
            showReceivedToast(backendAPI,newest);
          }
          if(newest) lastReceivedRef.current=newest.path;
          setStatus(x=>({...x,...s}));
        }
      }catch(e){setErr("Status: "+String(e.message||e));}
    }

    async function selectFile(p){
      try{await deckyCall("select_file",{path:p});await refreshStatus();setErr("");}
      catch(e){setErr("Selection: "+String(e.message||e));}
    }
    async function deleteReceived(p){
      if(deleteArmed!==p){setDeleteArmed(p);return;}
      try{
        setDeleteArmed(null);
        const r=await deckyCall("delete_received",{path:p});
        setStatus(s=>({...s,received:(r&&r.received)?r.received:((s.received||[]).filter(x=>x.path!==p))}));
        setErr("");
      }catch(e){setDeleteArmed(null);setErr("Delete: "+String(e.message||e));}
    }
    async function clearSelection(){
      try{await deckyCall("clear_selection");await refreshStatus();setErr("");}
      catch(e){setErr("Clear selection: "+String(e.message||e));}
    }

    function resetRemoteDummy(){
      const t=remoteTimerRef.current||{};
      if(t.resolve) clearTimeout(t.resolve);
      if(t.interval) clearInterval(t.interval);
      remoteTimerRef.current={resolve:null,interval:null};
      setRemoteState("idle");
      setRemoteProgress(0);
    }

    function startRemoteDummy(){
      resetRemoteDummy();
      const email=String(remoteEmail||"").trim();
      if(!status.selected){setErr("Send to User: choose a file first.");return;}
      if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){setErr("Send to User: enter a valid email.");return;}
      setErr("");
      setRemoteState("resolving");
      remoteTimerRef.current.resolve=setTimeout(()=>{
        setRemoteState("connecting");
        setTimeout(()=>{
          setRemoteState("sending");
          let p=0;
          remoteTimerRef.current.interval=setInterval(()=>{
            p=Math.min(100,p+8);
            setRemoteProgress(p);
            if(p>=100){
              clearInterval(remoteTimerRef.current.interval);
              remoteTimerRef.current.interval=null;
              setRemoteState("sent");
            }
          },180);
        },650);
      },700);
    }

    useEffect(()=>{bootstrap()},[]);
    useEffect(()=>{if(!status)return;let t=setInterval(refreshStatus,1000);return()=>clearInterval(t)},[!!status]);
    useEffect(()=>()=>{const t=remoteTimerRef.current||{};if(t.resolve)clearTimeout(t.resolve);if(t.interval)clearInterval(t.interval);},[]);

    const conns=(status&&status.addresses)||[];
    const activeConn=conns[Math.min(connIndex,Math.max(0,conns.length-1))]||null;
    const displayUrl=activeConn?activeConn.url:(status&&status.address)||"";
    const displayQr=activeConn?activeConn.qr_data:(status&&status.qr_data)||null;

    if(err&&!status)return h("div",{style:{padding:12}},h("div",{style:{marginBottom:10}},err),h(Btn,{onClick:bootstrap},"Retry backend"));
    if(!status)return h("div",{style:{padding:12}},"Starting DeckyShare backend…");
    return h("div",{style:{padding:"4px 8px 16px",fontSize:14,color:"white",background:"linear-gradient(180deg,rgba(5,18,34,.22),rgba(4,13,25,.08))"}},
      h("div",{style:{display:"flex",alignItems:"center",gap:10,padding:"8px 4px 11px"}},
        h("div",{style:{fontSize:30,lineHeight:1}},"◉"),
        h("div",{style:{flex:1}},h("div",{style:{display:"flex",alignItems:"center",gap:7}},h("div",{style:{fontWeight:800,fontSize:20,letterSpacing:.2}},"DeckyShare"),h("span",{style:{fontSize:9,fontWeight:800,padding:"2px 6px",borderRadius:999,background:"rgba(80,160,255,.18)",border:"1px solid rgba(100,180,255,.34)",color:"#9fd4ff"}},"REMOTE DEMO")),h("div",{style:{fontSize:11,color:"#9fc7ff"}},"Share files with your Steam Deck. Simple. Wireless. Fast."))
      ),
      h(Card,{style:{border:"1px solid rgba(66,153,255,.35)",boxShadow:"0 8px 22px rgba(0,0,0,.18)"}},
        h(SectionTitle,{icon:"📡",title:"Connect phone / PC",sub:"Open this address on your phone or computer"}),
        h("div",{style:{display:"flex",alignItems:"center",gap:7,fontSize:12,color:status.server_self_test?"#7ef29a":"#ffb3b3",marginBottom:8}},
          h("span",{style:{width:8,height:8,borderRadius:"50%",background:status.server_self_test?"#38e879":"#ff7070"}}),
          status.server_self_test?`Server OK • ${status.listen}`:"Server self-test failed"
        ),
        h("div",{style:{display:"flex",gap:10,alignItems:"stretch"}},
          h("div",{style:{flex:1,minWidth:0,display:"flex",alignItems:"center",justifyContent:"center",background:"rgba(43,112,196,.25)",border:"1px solid rgba(79,164,255,.42)",borderRadius:11,padding:"8px 5px",fontSize:10,fontWeight:700,whiteSpace:"nowrap",letterSpacing:"-.25px",color:"#69c6ff"}},displayUrl),
          displayQr&&h("div",{style:{width:92,flex:"0 0 92px",textAlign:"center"}},h("img",{src:displayQr,style:{display:"block",width:80,height:80,background:"white",padding:4,borderRadius:9,margin:"0 auto 3px"}}),h("div",{style:{fontSize:9,opacity:.65}},"Scan QR"))
        ),
        conns.length>1&&h("div",{style:{marginTop:7}},conns.map((c,i)=>h("button",{key:c.ip,onClick:()=>setConnIndex(i),style:{padding:"5px 7px",margin:"2px",borderRadius:7,border:i===connIndex?"1px solid #66c0f4":"1px solid rgba(255,255,255,.12)",background:i===connIndex?"rgba(102,192,244,.18)":"transparent",color:"white",fontSize:11}},c.interface)))
      ),

      h(Card,{style:{border:"1px solid rgba(66,153,255,.26)"}},
        h(SectionTitle,{icon:"📁",title:"Browse Files",sub:"Tap a folder to open it"}),
        !status.selected&&!path&&h("div",{style:{display:"grid",gridTemplateColumns:"1fr 1fr",gap:7}},
          roots.map(r=>h("button",{key:r.path,onClick:()=>browse(r.path),style:{minHeight:64,padding:"11px 10px",borderRadius:12,border:"1px solid rgba(104,170,255,.30)",background:"linear-gradient(145deg,rgba(35,77,128,.78),rgba(23,50,84,.78))",color:"white",fontWeight:700,textAlign:"left",fontSize:13,boxShadow:"inset 0 1px 0 rgba(255,255,255,.05)"}},`${r.name.startsWith("Drive:")?"💾":"📂"}  ${r.name}   ›`))
        ),
        status.selected?h("div",{style:{background:"rgba(67,151,222,.13)",borderRadius:10,padding:10}},
          h("div",{style:{fontWeight:700,wordBreak:"break-word"}},"✓ "+status.selected.name),
          h("div",{style:{opacity:.65,fontSize:11,marginTop:3}},status.selected.size_human),
          h(Btn,{onClick:clearSelection},"Choose another file")
        ):path&&h("div",{style:{marginTop:0}},
          h("div",{style:{display:"flex",gap:6}},h("button",{onClick:()=>{setPath(null);setParent(null);setItems([]);setErr("");},style:{flex:1,padding:8,borderRadius:9,border:"1px solid rgba(102,192,244,.35)",background:"rgba(102,192,244,.12)",color:"white",fontWeight:700}},"← Locations"),parent&&h("button",{onClick:()=>browse(parent),style:{flex:1,padding:8,borderRadius:9,border:"1px solid rgba(255,255,255,.14)",background:"transparent",color:"white"}},"↑ Up")),
          h("div",{style:{fontSize:10,opacity:.55,wordBreak:"break-all",margin:"7px 1px"}},path),
          items.slice(0,100).map(it=>h(Btn,{key:it.path,onClick:()=>it.type==="dir"?browse(it.path):selectFile(it.path)},it.type==="dir"?`📁 ${it.name}  ›`:`📄 ${it.name}  •  ${it.size_human}`))
        )
      ),

      h(Card,{style:{border:"1px solid rgba(92,168,255,.30)",boxShadow:"0 8px 22px rgba(0,0,0,.14)"}},
        h(SectionTitle,{icon:"🌐",title:"Send to User",sub:"Prototype • email-based remote transfer"}),
        h("div",{style:{fontSize:11,opacity:.68,lineHeight:1.45,marginBottom:8}},"Test the Blip-style flow. This prototype does not upload the file anywhere."),
        h("input",{
          type:"email",
          value:remoteEmail,
          disabled:remoteState!=="idle"&&remoteState!=="sent",
          placeholder:"friend@gmail.com",
          onChange:e=>{setRemoteEmail(e.target.value);if(remoteState==="sent")resetRemoteDummy();},
          style:{width:"100%",padding:"11px 12px",borderRadius:10,border:"1px solid rgba(112,179,255,.32)",background:"rgba(10,27,47,.72)",color:"white",fontSize:13,outline:"none",marginBottom:7}
        }),
        status.selected
          ? h("div",{style:{fontSize:11,background:"rgba(67,151,222,.10)",border:"1px solid rgba(102,192,244,.18)",borderRadius:9,padding:9,marginBottom:7,wordBreak:"break-word"}},"📄 "+status.selected.name+" • "+status.selected.size_human)
          : h("div",{style:{fontSize:11,opacity:.55,padding:"5px 1px 9px"}},"Choose a file above first."),
        h("button",{
          onClick:startRemoteDummy,
          disabled:!status.selected||(remoteState!=="idle"&&remoteState!=="sent"),
          style:{width:"100%",padding:"11px 12px",borderRadius:10,border:"1px solid rgba(92,168,255,.35)",background:(!status.selected||(remoteState!=="idle"&&remoteState!=="sent"))?"rgba(255,255,255,.05)":"linear-gradient(180deg,rgba(42,104,171,.72),rgba(24,65,112,.72))",color:"white",fontWeight:750,fontSize:13}
        },remoteState==="resolving"?"Finding user…":remoteState==="connecting"?"Connecting…":remoteState==="sending"?"Sending…":remoteState==="sent"?"Send again":"Send to user"),
        remoteState!=="idle"&&h("div",{style:{marginTop:9}},
          h("div",{style:{fontSize:11,opacity:.75,marginBottom:5}},
            remoteState==="resolving"?"Resolving "+remoteEmail+"…":
            remoteState==="connecting"?"User found • establishing secure connection…":
            remoteState==="sending"?remoteProgress+"% • simulated transfer":
            "✓ Sent to "+remoteEmail+" (prototype)"
          ),
          (remoteState==="sending"||remoteState==="sent")&&h(Bar,{value:remoteState==="sent"?100:remoteProgress})
        ),
        h("div",{style:{fontSize:9,opacity:.42,marginTop:7}},"Prototype only • no account lookup • no internet transfer • no relay")
      ),

      h(Card,{style:{border:"1px solid rgba(130,92,255,.26)"}},
        h(SectionTitle,{icon:"📥",title:"Received Files",sub:"Files received from phone / PC"}),
        h("div",{style:{fontSize:10,opacity:.55,margin:"-2px 0 7px",wordBreak:"break-all"}},"Saved to "+(status.receive_dir||"Downloads/DeckShare")),
        (!status.received||!status.received.length)?h("div",{style:{opacity:.55,padding:"7px 0",fontSize:12}},"No received files yet"):
          status.received.map(f=>h("div",{key:f.path,style:{background:"rgba(28,54,87,.72)",border:"1px solid rgba(120,180,255,.16)",borderRadius:11,padding:10,margin:"7px 0"}},
            h("div",{style:{display:"flex",gap:9,alignItems:"center"}},
              h("div",{style:{width:38,height:38,borderRadius:9,display:"flex",alignItems:"center",justifyContent:"center",fontSize:23,background:"rgba(120,77,255,.20)",border:"1px solid rgba(151,113,255,.24)"}},"📦"),
              h("div",{style:{minWidth:0,flex:1}},h("div",{style:{fontWeight:700,wordBreak:"break-word"}},f.name),h("div",{style:{fontSize:10,opacity:.6,wordBreak:"break-all",marginTop:2}},f.size_human+" • "+f.path))
            ),
            h("button",{onClick:()=>deleteReceived(f.path),style:{marginTop:7,padding:"6px 9px",borderRadius:8,border:"1px solid rgba(255,110,110,.38)",background:deleteArmed===f.path?"rgba(255,70,70,.28)":"rgba(255,70,70,.10)",color:"#ffd0d0",fontSize:12}},deleteArmed===f.path?"Tap again to delete":"Delete")
          ))
      ),

      h(Card,{style:{border:"1px solid rgba(72,205,178,.20)"}},
        h(SectionTitle,{icon:"↔️",title:"Live Transfers",sub:"Speed and progress"}),
        (!status.transfers||!status.transfers.length)?h("div",{style:{opacity:.55,padding:"5px 0",fontSize:12}},"No active transfers"):
          status.transfers.map(t=>h("div",{key:t.id,style:{padding:"7px 0"}},h("div",{style:{fontWeight:650}},`${t.direction==="upload"?"Phone/PC → Deck":"Deck → Phone/PC"}: ${t.name}`),h("div",{style:{fontSize:11,opacity:.65,marginTop:2}},`${Number(t.percent||0).toFixed(1)}% • ${fmt(t.speed)}/s${t.eta?` • ETA ${Math.ceil(t.eta)}s`:""}`),h(Bar,{value:t.percent})))
      ),
      h(Card,{style:{border:"1px solid rgba(255,190,75,.22)"}},
        h(SectionTitle,{icon:"☕",title:"Support DeckyShare",sub:"Free & open-source community project"}),
        h("div",{style:{fontSize:11,opacity:.72,lineHeight:1.45,marginBottom:7}},"Enjoying DeckyShare? You can support future development."),
        h("button",{onClick:()=>{try{window.open("https://buymeacoffee.com/Gillrv","_blank")}catch(e){}},style:{width:"100%",padding:"10px 12px",borderRadius:10,border:"1px solid rgba(255,196,92,.38)",background:"rgba(255,183,65,.13)",color:"#ffe0a3",fontWeight:750,fontSize:13}},"☕ Buy me a coffee")
      ),
      err&&h("div",{style:{color:"#ffb3b3",marginTop:8,wordBreak:"break-word"}},err)
    );
  }
}

export default function(){
  const Panel=makePanel();
  let notifyAPI=null, receiveListener=null;
  try{
    notifyAPI=connectDeckyBackend();
    if(notifyAPI && typeof notifyAPI.addEventListener==="function"){
      receiveListener=(...args)=>{
        const raw=args.length?args[args.length-1]:null;
        showReceivedToast(notifyAPI,raw);
      };
      notifyAPI.addEventListener("file_received",receiveListener);
    }
  }catch(e){console.error("[DeckShare] global receive notifications unavailable",e);}
  return {
    name:"DeckyShareRemoteDemo",
    titleView:h("div",{style:{fontWeight:700}},"DeckyShare Remote Demo"),
    content:h(Panel),
    icon:h("div",{style:{fontSize:20}},"↔"),
    onDismount(){
      try{
        if(notifyAPI&&receiveListener&&typeof notifyAPI.removeEventListener==="function"){
          notifyAPI.removeEventListener("file_received",receiveListener);
        }
      }catch(e){}
      console.log("DeckShare UI unloaded");
    }
  };
}
