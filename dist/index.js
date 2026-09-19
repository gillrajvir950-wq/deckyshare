const React = window.SP_REACT || window.React;
const h = React.createElement;
const { useEffect, useRef, useState } = React;

function Card({children}) {
  return h("div",{style:{background:"linear-gradient(180deg,rgba(22,42,68,.92),rgba(15,29,49,.92))",border:"1px solid rgba(120,180,255,.20)",borderRadius:14,padding:12,margin:"9px 0"}},children);
}
function Btn({children,onClick,disabled=false}) {
  return h("button",{disabled,onClick,style:{width:"100%",padding:"12px 13px",margin:"6px 0",borderRadius:12,border:"1px solid rgba(130,190,255,.25)",background:disabled?"rgba(255,255,255,.05)":"linear-gradient(180deg,rgba(44,79,120,.60),rgba(25,48,78,.60))",color:"white",fontSize:14,textAlign:"center",fontWeight:700}},children);
}
function Bar({value}) {
  return h("div",{style:{height:9,borderRadius:7,background:"rgba(255,255,255,.14)",overflow:"hidden",marginTop:9}},
    h("div",{style:{height:"100%",width:value+"%",background:"#66c0f4",transition:"width .25s ease"}}));
}
function Panel(){
  const [email,setEmail]=useState("");
  const [state,setState]=useState("idle");
  const [progress,setProgress]=useState(0);
  const timer=useRef(null);
  useEffect(()=>()=>{if(timer.current)clearInterval(timer.current)},[]);
  const labels={idle:"Ready",finding:"Finding user…",connecting:"Connecting…",sending:"Sending…",sent:"Sent ✓"};
  function send(){
    if(!email.trim() || state!=="idle") return;
    setProgress(0); setState("finding");
    setTimeout(()=>setState("connecting"),700);
    setTimeout(()=>{
      setState("sending");
      let p=0;
      timer.current=setInterval(()=>{
        p=Math.min(100,p+8); setProgress(p);
        if(p>=100){clearInterval(timer.current);timer.current=null;setState("sent");}
      },140);
    },1400);
  }
  function reset(){if(timer.current)clearInterval(timer.current);timer.current=null;setState("idle");setProgress(0);}
  return h("div",{style:{padding:"5px 8px 16px",fontSize:14,color:"white"}},
    h("div",{style:{display:"flex",alignItems:"center",gap:9,padding:"8px 4px 10px"}},
      h("div",{style:{fontSize:28}},"🌐"),
      h("div",null,
        h("div",{style:{fontWeight:800,fontSize:19}},"DeckyShare Remote Demo"),
        h("div",{style:{fontSize:11,opacity:.68}},"UX prototype — no real transfer")
      )
    ),
    h(Card,null,
      h("div",{style:{fontWeight:800,fontSize:16,marginBottom:3}},"Send to User"),
      h("div",{style:{fontSize:11,opacity:.66,marginBottom:10}},"Try the email-based remote-send flow before we build networking."),
      h("input",{value:email,onChange:e=>setEmail(e.target.value),placeholder:"Recipient email",disabled:state!=="idle",style:{boxSizing:"border-box",width:"100%",padding:"11px 12px",borderRadius:10,border:"1px solid rgba(130,190,255,.28)",background:"rgba(0,0,0,.20)",color:"white",fontSize:14,outline:"none"}}),
      h("div",{style:{marginTop:10,padding:"10px",borderRadius:10,background:"rgba(255,255,255,.05)"}},
        h("div",{style:{fontSize:11,opacity:.6}},"Demo file"),
        h("div",{style:{fontWeight:700,marginTop:2}},"Cyberpunk2077-save.zip"),
        h("div",{style:{fontSize:11,opacity:.6,marginTop:2}},"128 MB")
      ),
      state==="idle"
        ? h(Btn,{onClick:send,disabled:!email.trim()},"Send to user")
        : h("div",{style:{marginTop:10}},
            h("div",{style:{display:"flex",justifyContent:"space-between",fontSize:12}},h("span",null,labels[state]),h("span",null,state==="sending"||state==="sent"?progress+"%":"")),
            h(Bar,{value:state==="sent"?100:progress}),
            state==="sent"&&h(Btn,{onClick:reset},"Try again")
          )
    ),
    h("div",{style:{fontSize:10,opacity:.55,textAlign:"center",padding:"7px"}},"Prototype only • no account lookup • no internet transfer • no relay")
  );
}
export default function(){
  return {
    name:"DeckyShareRemoteDemo",
    titleView:h("div",{style:{fontWeight:700}},"DeckyShare Remote Demo"),
    content:h(Panel),
    icon:h("div",{style:{fontSize:20}},"🌐")
  };
}
