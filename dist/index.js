const React=window.SP_REACT||window.React;
const h=React.createElement;
const {useEffect,useState}=React;

function api(){
  const x=window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
  if(!x||typeof x.connect!=="function") return null;
  try{return x.connect(2,"DeckyShareRemoteDemo")}catch(e){try{return x.connect(1,"DeckyShareRemoteDemo")}catch(_){return null}}
}
const C={
  page:{padding:"7px 8px 18px",color:"#fff"},
  card:{padding:12,borderRadius:14,background:"linear-gradient(180deg,rgba(23,48,82,.96),rgba(14,31,55,.96))",border:"1px solid rgba(94,164,255,.28)",marginBottom:9},
  button:{width:"100%",padding:"11px 10px",borderRadius:11,border:"1px solid rgba(109,174,255,.32)",background:"linear-gradient(180deg,rgba(35,113,220,.96),rgba(22,83,178,.96))",color:"#fff",fontWeight:800,fontSize:13},
  secondary:{width:"100%",padding:"10px",borderRadius:10,border:"1px solid rgba(255,255,255,.14)",background:"rgba(255,255,255,.07)",color:"#fff",fontWeight:700}
};
function Panel(){
  const [info,setInfo]=useState({busy:true,ok:false,local:"0.2.0-SSL1",remote:"—",available:false,msg:"Checking for updates…"});
  const [installing,setInstalling]=useState(false);
  async function check(){
    setInfo(v=>({...v,busy:true,msg:"Checking for updates…"}));
    const b=api(); if(!b){setInfo(v=>({...v,busy:false,ok:false,msg:"Backend not connected"}));return}
    try{
      const q=await b.call("updater_status"),r=q&&q.result!==undefined?q.result:q;
      if(!r||!r.ok) throw new Error(r?.error||"Unknown updater error");
      setInfo({busy:false,ok:true,local:r.local,remote:r.remote,available:!!r.available,msg:r.available?"A newer version is available.":"You are up to date."});
    }catch(e){setInfo(v=>({...v,busy:false,ok:false,msg:(e&&e.message)||String(e)}))}
  }
  async function install(){
    const b=api(); if(!b){setInfo(v=>({...v,ok:false,msg:"Backend not connected"}));return}
    setInstalling(true);
    try{
      const q=await b.call("updater_apply"),r=q&&q.result!==undefined?q.result:q;
      if(!r||!r.ok) throw new Error(r?.error||"Update failed");
      setInfo(v=>({...v,busy:false,ok:true,available:false,local:r.version,msg:"Update installed. Reload DeckyShare Remote Demo."}));
    }catch(e){setInfo(v=>({...v,ok:false,msg:(e&&e.message)||String(e)}))}
    setInstalling(false);
  }
  useEffect(()=>{check()},[]);
  return h("div",{style:C.page},
    h("div",{style:{display:"flex",alignItems:"center",justifyContent:"space-between",margin:"6px 2px 10px"}},
      h("div",null,h("div",{style:{fontSize:19,fontWeight:900}},"🌐 DeckyShare Remote"),h("div",{style:{fontSize:10,opacity:.62}},"Share • Transfer • Manage")),
      h("div",{style:{fontSize:10,fontWeight:800,padding:"5px 8px",borderRadius:12,background:"rgba(255,255,255,.08)"}},info.local)
    ),
    h("div",{style:C.card},
      h("div",{style:{display:"flex",alignItems:"center",gap:9}},
        h("div",{style:{fontSize:24}},info.available?"⬇️":info.ok?"✅":"⚠️"),
        h("div",{style:{flex:1}},h("div",{style:{fontSize:17,fontWeight:900}},info.busy?"Checking…":info.available?"Update Available":info.ok?"Updater Ready":"Updater Error"),
          h("div",{style:{fontSize:11,opacity:.72,marginTop:2}},info.msg)),
        info.available&&h("div",{style:{fontSize:11,fontWeight:900,padding:"5px 7px",borderRadius:10,background:"rgba(35,177,91,.28)"}},info.remote)
      ),
      h("div",{style:{fontSize:11,opacity:.72,marginTop:9}},"Local: "+info.local+"  |  Remote: "+info.remote)
    ),
    info.available&&h("div",{style:C.card},
      h("div",{style:{fontSize:14,fontWeight:900,marginBottom:6}},"What's new in "+info.remote),
      h("div",{style:{fontSize:11,lineHeight:1.55,opacity:.78}},"• Improved updater reliability",h("br"),"• SteamOS certificate handling",h("br"),"• Stability improvements")
    ),
    info.available&&h("button",{disabled:installing,onClick:install,style:C.button},installing?"Installing…":"⬇  Install Update "+info.remote),
    h("div",{style:{height:7}}),
    h("button",{disabled:info.busy||installing,onClick:check,style:C.secondary},"↻  Check Again"),
    h("div",{style:{...C.card,marginTop:9,marginBottom:0,background:info.ok?"rgba(13,91,70,.40)":"rgba(110,52,52,.35)",border:info.ok?"1px solid rgba(48,220,151,.35)":"1px solid rgba(255,115,115,.3)"}},
      h("div",{style:{fontSize:12,fontWeight:850}},info.ok?"✓ Connection successful":"! Connection issue"),
      h("div",{style:{fontSize:10,opacity:.7,marginTop:2}},info.ok?"GitHub reachable. Updater backend ready.":info.msg)
    ),
    h("div",{style:{fontSize:9,opacity:.45,textAlign:"center",marginTop:9}},"Remote Demo • updater UI v0.2.2")
  )
}
export default function(){return{name:"DeckyShareRemoteDemo",titleView:h("div",{style:{fontWeight:800}},"DeckyShare Remote Demo"),content:h(Panel),icon:h("div",{style:{fontSize:20}},"🌐")}}
