"""Phone / PC web page served by DeckyShare.

The upload engine (_CORE_JS: Maximum Speed, Turbo, Fast and Reliable modes,
pause, resume, cancel) is kept verbatim from RC11.29; RC11.33 only replaced the
layout, styling and the display code (_UI_JS).
"""
import html

_CSS = r"""
*{box-sizing:border-box}
:root{--bg:#0b1118;--card:#131c27;--card2:#10171f;--line:#22303f;--line2:#2c4057;--text:#e8eef5;--muted:#9aabbd;--dim:#6f8399;--accent:#1a9fff;--accent-ink:#06121f;--good:#3ddc84;--warn:#ffb454;--bad:#ff9a9a}
html{color-scheme:dark;-webkit-text-size-adjust:100%}
body{margin:0;min-height:100vh;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
padding:max(16px,env(safe-area-inset-top)) max(16px,env(safe-area-inset-right)) max(24px,env(safe-area-inset-bottom)) max(16px,env(safe-area-inset-left))}
.wrap{max-width:520px;margin:0 auto;display:flex;flex-direction:column;gap:16px}
button,.btn{font:inherit;cursor:pointer}
.hidden{display:none!important}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
header{display:flex;align-items:center;gap:10px;padding-top:4px}
.logo{width:38px;height:38px;flex:none;border-radius:11px;background:var(--accent);display:flex;align-items:center;justify-content:center}
.brand{font-size:21px;font-weight:800;letter-spacing:-.3px}
.status{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:#9fe0b8}
.status i{width:7px;height:7px;border-radius:50%;background:var(--good)}
.status.off{color:#ffd08a}.status.off i{background:var(--warn)}
.tabs{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1.38fr) minmax(0,.7fr);gap:4px;padding:4px;background:var(--card);border:1px solid var(--line);border-radius:14px}
.tab{min-height:46px;border:0;border-radius:10px;background:transparent;color:#c9d6e3;font-size:15px;font-weight:700;display:flex;align-items:center;justify-content:center;gap:6px;white-space:nowrap;padding:0 4px}
.tab .badge{font-size:10px;padding:1px 6px}
.tab[aria-selected=true]{background:var(--accent);color:var(--accent-ink);font-weight:800}
.badge{font-size:11px;font-weight:800;color:var(--accent-ink);background:var(--warn);border-radius:999px;padding:1px 7px}
.panel{display:flex;flex-direction:column;gap:14px}
.drop{border:2px dashed var(--line2);border-radius:18px;background:#101923;padding:24px 18px;display:flex;flex-direction:column;align-items:center;gap:9px;text-align:center}
.drop.over{border-color:var(--accent);background:#12273d}
.drop-icon{width:54px;height:54px;border-radius:16px;background:#12273d;display:flex;align-items:center;justify-content:center}
.drop h2{margin:0;font-size:18px}
.drop p{margin:0;font-size:13px;color:var(--muted);line-height:1.4;max-width:270px}
.pick{margin-top:4px;min-height:48px;padding:0 22px;border-radius:12px;background:#1d2b3b;border:1px solid var(--line2);color:var(--text);font-size:15px;font-weight:700;display:inline-flex;align-items:center;gap:8px}
.pick:focus-within{outline:2px solid var(--accent);outline-offset:2px}
.section-head{display:flex;justify-content:space-between;align-items:baseline;padding:0 2px;font-size:12px;color:var(--dim)}
.section-head b{font-weight:700;letter-spacing:.8px;text-transform:uppercase}
.list{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.item{display:flex;align-items:center;gap:12px;padding:10px 8px 10px 14px;border-top:1px solid #1d2835}
.item:first-child{border-top:0}
.item .meta{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.item .name{font-size:14px;font-weight:700;overflow-wrap:anywhere}
.item .sub{font-size:12px;color:var(--muted)}
.item .state{font-size:12px;font-weight:700;color:var(--muted);padding-right:6px;white-space:nowrap}
.item .state.on{color:#7cc4ff}.item .state.ok{color:var(--good)}.item .state.bad{color:var(--bad)}
.x{width:44px;height:44px;flex:none;border:0;border-radius:10px;background:transparent;display:flex;align-items:center;justify-content:center}
.x:hover{background:#1d2b3b}
.primary{min-height:56px;border:0;border-radius:14px;background:var(--accent);color:var(--accent-ink);font-size:17px;font-weight:800;display:flex;align-items:center;justify-content:center;gap:9px;width:100%;text-decoration:none}
.primary:disabled{opacity:.45;cursor:default}
.option{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;background:var(--card2);border:1px solid #1d2835;border-radius:12px;cursor:pointer}
.option b{font-size:14px;display:block}
.option small{display:block;margin-top:2px;font-size:12px;color:var(--muted);line-height:1.35}
.switch{position:relative;width:50px;height:30px;flex:none}
.switch input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer}
.switch span{position:absolute;inset:0;border-radius:999px;background:#2c3a4a;transition:background .15s}
.switch span::after{content:"";position:absolute;top:3px;left:3px;width:24px;height:24px;border-radius:50%;background:#fff;transition:transform .15s}
.switch input:checked+span{background:var(--accent)}
.switch input:checked+span::after{transform:translateX(20px)}
.switch input:focus-visible+span{outline:2px solid var(--accent);outline-offset:2px}
.switch input:disabled+span{opacity:.5}
.tip{display:flex;gap:10px;align-items:flex-start;font-size:12px;color:var(--muted);line-height:1.45;padding:0 4px}
.tip svg{flex:none;margin-top:1px}
.xfer{background:var(--card);border:1px solid var(--line2);border-radius:20px;padding:18px;display:flex;flex-direction:column;gap:12px}
.xfer.done{border-color:#2f6b4a}
.xfer-top{display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:12px}
.xfer-top b{font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:#7cc4ff}
.xfer.done .xfer-top b{color:var(--good)}
.xfer-top span{color:var(--muted)}
.xfer-name{font-size:16px;font-weight:700;overflow-wrap:anywhere}
.xfer-size{font-size:13px;color:var(--muted);margin-top:3px}
.pct{display:flex;align-items:baseline;gap:4px;font-weight:800;line-height:1}
.pct span:first-child{font-size:54px;letter-spacing:-2px}
.pct span:last-child{font-size:22px;color:var(--muted)}
.bar{height:12px;border-radius:999px;background:var(--line);overflow:hidden}
.fill{height:100%;width:0;border-radius:999px;background:var(--accent);transition:width .25s}
.xfer.done .fill{background:var(--good)}
.stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.stat{background:#0f1720;border-radius:12px;padding:10px 12px;display:flex;flex-direction:column;gap:2px}
.stat small{font-size:11px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;color:var(--dim)}
.stat b{font-size:20px;font-weight:800}
.warn{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border-radius:12px;background:#2a1f0e;border:1px solid #6b4a17;color:#ffd08a;font-size:13px;line-height:1.4}
.actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.actions.one{grid-template-columns:1fr}
.secondary{min-height:48px;border-radius:12px;border:1px solid var(--line2);background:#1d2b3b;color:var(--text);font-size:15px;font-weight:700}
.danger{min-height:48px;border-radius:12px;border:1px solid #5a2a2a;background:transparent;color:var(--bad);font-size:15px;font-weight:700}
.note{font-size:12px;color:var(--muted);line-height:1.4;min-height:0}
.diag{font-size:11px;color:var(--dim)}
.file-card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;display:flex;gap:14px;align-items:center}
.file-icon{width:46px;height:46px;flex:none;border-radius:12px;background:#1d2b3b;display:flex;align-items:center;justify-content:center}
.empty{background:var(--card);border:1px dashed var(--line2);border-radius:16px;padding:22px 18px;text-align:center;color:var(--muted);font-size:14px;line-height:1.5}
.empty b{display:block;color:var(--text);font-size:16px;margin-bottom:4px}
@media (max-width:380px){.tab{font-size:13px;gap:5px}}
.compose{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px;display:flex;flex-direction:column;gap:10px}
.compose textarea{width:100%;min-height:92px;resize:vertical;border:1px solid var(--line2);border-radius:12px;background:#0d151e;color:var(--text);font:inherit;font-size:16px;line-height:1.4;padding:10px 12px}
.compose textarea:focus{outline:2px solid var(--accent);outline-offset:1px}
.compose-row{display:flex;gap:10px}.compose-row .primary{flex:1;min-height:50px;font-size:16px}.compose-row .secondary{padding:0 18px}
.titem{padding:12px 14px;border-top:1px solid #1d2835;display:flex;flex-direction:column;gap:8px}
.titem:first-child{border-top:0}
.ttext{font-size:15px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere;max-height:9.5em;overflow:hidden}
.ttext a{color:#7cc4ff}
.tfoot{display:flex;align-items:center;gap:8px}
.tmeta{flex:1;min-width:0;font-size:12px;color:var(--muted)}
.chip{min-height:38px;padding:0 14px;border-radius:10px;border:1px solid var(--line2);background:#1d2b3b;color:var(--text);font-size:14px;font-weight:700;display:inline-flex;align-items:center;gap:6px;text-decoration:none}
.chip.ok{border-color:#2f6b4a;color:var(--good)}
.chip.del{width:38px;padding:0;justify-content:center;background:transparent;border-color:transparent}
.gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.shot{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
.shot img{display:block;width:100%;aspect-ratio:16/10;object-fit:cover;background:#0d151e;-webkit-touch-callout:default}
.shot a{margin:8px;min-height:38px;border-radius:10px;border:1px solid var(--line2);background:#1d2b3b;color:var(--text);font-size:14px;font-weight:700;display:flex;align-items:center;justify-content:center;gap:6px;text-decoration:none}
footer{margin-top:6px;text-align:center;font-size:12px;color:var(--dim);line-height:1.6}
footer code{color:#7cc4ff;font-size:12px}
footer a{color:#7cc4ff}
"""

_BODY = r"""<div class="wrap">
<header><div class="logo"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06121f" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 7h11l-3-3M17 17H6l3 3"/></svg></div><div><div class="brand">DeckyShare</div><div id="conn" class="status"><i></i><span>Connected to Steam Deck</span></div></div></header>

<section id="xfer" class="xfer hidden" aria-live="polite">
<div class="xfer-top"><b id="xlabel">Sending to Deck</b><span id="xmode"></span></div>
<div><div id="xname" class="xfer-name"></div><div id="xsize" class="xfer-size"></div></div>
<div class="pct"><span id="xpct">0</span><span>%</span></div>
<div class="bar"><div id="upbar" class="fill"></div></div>
<div class="stats"><div class="stat"><small>Speed now</small><b id="xspeed">–</b></div><div class="stat"><small>Time left</small><b id="xeta">–</b></div></div>
<div id="xstall" class="warn hidden"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffb454" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex:none;margin-top:1px"><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg><span><b id="xstallfor">No data for a few seconds.</b> Keep this screen on and stay near the router.</span></div>
<div id="xactions" class="actions"><button id="pause" class="secondary" disabled>Pause</button><button id="cancel" class="danger" disabled>Cancel</button></div>
<div id="uptext" class="note"></div>
<div id="queue" class="list hidden"></div>
<div id="diag" class="diag"></div>
</section>

<div class="tabs" role="tablist" aria-label="Transfer direction">
<button id="tab-send" class="tab" role="tab" aria-selected="true" aria-controls="panel-send">Send to Deck</button>
<button id="tab-get" class="tab" role="tab" aria-selected="false" aria-controls="panel-get">Get from Deck <span id="getbadge" class="badge hidden">1</span></button>
<button id="tab-text" class="tab" role="tab" aria-selected="false" aria-controls="panel-text">Text <span id="textbadge" class="badge hidden">1</span></button>
</div>

<section id="panel-send" class="panel" role="tabpanel" aria-labelledby="tab-send">
<div id="drop" class="drop">
<div class="drop-icon"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#1a9fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></svg></div>
<h2>Choose files to send</h2>
<p>Videos, photos, games, anything. Big files are fine.</p>
<label class="pick"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#c9d6e3" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg><span>Browse files</span><input id="file" class="sr" type="file" multiple></label>
</div>
<div id="pickedwrap" class="hidden">
<div class="section-head"><b>Ready to send</b><span id="pickedsum"></span></div>
<div id="picked" class="list" style="margin-top:8px"></div>
</div>
<button id="upload" class="primary" disabled><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06121f" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg><span id="uploadlabel">Send to Deck</span></button>
<label class="option" for="maxspeed"><span><b>Maximum Speed</b><small>Fastest. No resume: if Wi-Fi drops, the file starts again.</small></span><span class="switch"><input id="maxspeed" type="checkbox" checked><span></span></span></label>
<div class="tip"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9aabbd" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/></svg><span id="awake">Keep this screen on and the browser open while sending. Phones pause transfers in the background.</span></div>
</section>

<section id="panel-get" class="panel hidden" role="tabpanel" aria-labelledby="tab-get">
<div id="selected"><div class="empty"><b>Nothing shared yet</b>Pick a file in DeckyShare on your Steam Deck. It will show up here.</div></div>
<a id="download" class="primary hidden"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06121f" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v12M7 11l5 5 5-5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></svg><span>Download</span></a>
<div id="gallerywrap" class="hidden">
<div class="section-head"><b>Pictures from Deck</b><span id="gallerycount"></span></div>
<div class="tip" style="margin:8px 0 10px"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9aabbd" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5h16v14H4z"/><path d="M4 16l5-5 4 4 3-3 4 4"/></svg><span>On iPhone: press and hold a picture, then <b>Save to Photos</b>. Or tap Download.</span></div>
<div id="gallery" class="gallery"></div>
</div>
<div id="transferswrap" class="hidden"><div class="section-head"><b>From Deck</b></div><div id="transfers" class="list" style="margin-top:8px"></div></div>
</section>

<section id="panel-text" class="panel hidden" role="tabpanel" aria-labelledby="tab-text">
<div class="compose">
<label for="tinput" class="sr">Text or link to send</label>
<textarea id="tinput" placeholder="Type or paste text or a link" maxlength="20000"></textarea>
<div class="compose-row"><button id="tpaste" class="secondary hidden">Paste</button><button id="tsend" class="primary" disabled><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#06121f" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg><span>Send to Deck</span></button></div>
<div id="tnote" class="note"></div>
</div>
<div class="section-head"><b>Shared text</b><span id="tcount"></span></div>
<div id="tlist"><div class="empty"><b>No text yet</b>Send a link or a note to your Deck, or type one in DeckyShare on the Deck. It shows up here.</div></div>
</section>

<footer>Connected to <code>__ADDRESS__</code><br>Free and open source · <a href="https://buymeacoffee.com/Gillrv" target="_blank" rel="noopener">Buy me a coffee</a></footer>
</div>"""

_CORE_JS = r"""async function api(path,opt){const r=await fetch(path,opt);if(!r.ok)throw new Error(await r.text());return r;}
function fmt(n){if(n>=1073741824)return(n/1073741824).toFixed(1)+' GB';if(n>=1048576)return(n/1048576).toFixed(1)+' MB';if(n>=1024)return(n/1024).toFixed(1)+' KB';return Math.round(n||0)+' B';}
function escapeHtml(v){return String(v||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
let crcTable=null;function crc32(buf){if(!crcTable){crcTable=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=(c&1)?(0xedb88320^(c>>>1)):(c>>>1);crcTable[n]=c>>>0;}}let c=0xffffffff;for(let i=0;i<buf.length;i++)c=crcTable[(c^buf[i])&255]^(c>>>8);return((c^0xffffffff)>>>0).toString(16).padStart(8,'0');}
let crcWorker=null,crcJob=0,crcPending=new Map();
function getCrcWorker(){if(crcWorker)return crcWorker;try{const source=`self.onmessage=e=>{const buffer=e.data.buffer,b=new Uint8Array(buffer),t=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=(c&1)?(0xedb88320^(c>>>1)):(c>>>1);t[n]=c>>>0;}let c=0xffffffff;for(let i=0;i<b.length;i++)c=t[(c^b[i])&255]^(c>>>8);self.postMessage({id:e.data.id,sum:((c^0xffffffff)>>>0).toString(16).padStart(8,'0'),buffer},[buffer]);}`;crcWorker=new Worker(URL.createObjectURL(new Blob([source],{type:'text/javascript'})));crcWorker.onmessage=e=>{const p=crcPending.get(e.data.id);if(p){crcPending.delete(e.data.id);p.resolve({sum:e.data.sum,buffer:e.data.buffer});}};crcWorker.onerror=()=>{for(const p of crcPending.values())p.reject(new Error('CRC worker failed'));crcPending.clear();try{crcWorker.terminate();}catch(e){}crcWorker=null;};return crcWorker;}catch(e){return null;}}
async function crc32Async(buffer){const worker=getCrcWorker();if(!worker)return{sum:crc32(new Uint8Array(buffer)),buffer};const id=++crcJob;return new Promise((resolve,reject)=>{crcPending.set(id,{resolve,reject});try{worker.postMessage({id,buffer},[buffer]);}catch(e){crcPending.delete(id);reject(e);}});}
async function prepareUploadChunk(f,off,chunk){const end=Math.min(f.size,off+chunk),readStart=performance.now(),buffer=await f.slice(off,end).arrayBuffer(),readMs=performance.now()-readStart,crcStart=performance.now(),checked=await crc32Async(buffer),crcMs=performance.now()-crcStart;return{off,end,blob:checked.buffer,sum:checked.sum,readMs,crcMs};}
function showUploadDiagnostic(current,uploadMs,serverMs){const el=document.getElementById('diag');if(el)el.textContent=`Chunk diagnostic • Read ${Math.round(current.readMs)}ms • CRC ${Math.round(current.crcMs)}ms • Upload ${Math.round(uploadMs)}ms • Server ${Math.round(serverMs||0)}ms`;}
let wakeLock=null;
function setAwakeText(text){const el=document.getElementById('awake');if(el)el.textContent=text;}
async function requestTransferWakeLock(){
  if(!('wakeLock' in navigator)||!navigator.wakeLock||typeof navigator.wakeLock.request!=='function'){
    setAwakeText('Keep this screen on during large transfers. This browser does not expose screen-awake protection here.');
    return false;
  }
  try{
    if(wakeLock&&!wakeLock.released)return true;
    wakeLock=await navigator.wakeLock.request('screen');
    setAwakeText('✓ Screen-awake protection active during transfer');
    wakeLock.addEventListener('release',()=>{setAwakeText('Screen-awake protection released. Keep this page visible during large transfers.');});
    return true;
  }catch(e){
    setAwakeText('Keep this screen on during large transfers. Screen-awake protection was blocked by the browser.');
    return false;
  }
}
async function releaseTransferWakeLock(){
  try{if(wakeLock&&!wakeLock.released)await wakeLock.release();}catch(e){}
  wakeLock=null;
}
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='visible'&&uploadControl.running)requestTransferWakeLock();
});

let uploadControl={running:false,paused:false,cancelled:false,controller:null,controllers:[]},queueState=[];
function setQueueStatus(i,status){if(queueState[i]){queueState[i].status=status;renderQueue();}}
function cancelledError(){const e=new Error('Cancelled');e.cancelled=true;return e;}
async function waitWhilePaused(){while(uploadControl.paused&&!uploadControl.cancelled)await new Promise(r=>setTimeout(r,150));if(uploadControl.cancelled)throw cancelledError();}
function newUploadId(){return(globalThis.crypto&&crypto.randomUUID)?crypto.randomUUID():('ds_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,12));}
function trackUploadController(controller){uploadControl.controllers.push(controller);uploadControl.controller=controller;}
function untrackUploadController(controller){uploadControl.controllers=uploadControl.controllers.filter(x=>x!==controller);if(uploadControl.controller===controller)uploadControl.controller=uploadControl.controllers[uploadControl.controllers.length-1]||null;}
function abortActiveUploads(){for(const controller of [...uploadControl.controllers]){try{controller.abort();}catch(e){}}}
async function cancelPartial(name,uploadId){for(let i=0;i<3;i++){try{const r=await fetch('/api/cancel-upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,upload_id:uploadId})});if(r.ok)return;}catch(e){}await new Promise(r=>setTimeout(r,120));}}
async function uploadStatus(f,uploadId){const r=await fetch('/api/upload-status?upload_id='+encodeURIComponent(uploadId)+'&name='+encodeURIComponent(f.name)+'&total='+f.size,{cache:'no-store'});if(!r.ok)throw new Error(await r.text()||('Status error '+r.status));return r.json();}
async function stableCheckpoint(f,uploadId,fallback){let last=-1,same=0,best=fallback;for(let i=0;i<20;i++){try{const s=await uploadStatus(f,uploadId),n=Number(s.received||0);if(n>=0&&n<=f.size)best=n;if(n===last)same++;else same=0;last=n;if(s.complete||same>=1)return s;}catch(e){}await new Promise(r=>setTimeout(r,100));}return{received:best,complete:false,name:f.name};}
function fastUploadRequest(f,off,uploadId,onProgress){return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest(),url='/upload?name='+encodeURIComponent(f.name)+'&offset='+off+'&total='+f.size;xhr.open('PUT',url,true);xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.setRequestHeader('X-DeckyShare-Upload-ID',uploadId);xhr.setRequestHeader('X-DeckyShare-Fast','1');xhr.upload.onprogress=e=>onProgress(Math.min(f.size,off+Number(e.loaded||0)));xhr.onload=()=>{untrackUploadController(xhr);let data={};try{data=JSON.parse(xhr.responseText||'{}');}catch(e){}resolve({status:xhr.status,ok:xhr.status>=200&&xhr.status<300,data,text:xhr.responseText||''});};xhr.onerror=()=>{untrackUploadController(xhr);reject(new Error('Connection interrupted'));};xhr.onabort=()=>{untrackUploadController(xhr);const e=new Error('Upload paused');e.name='AbortError';reject(e);};trackUploadController(xhr);xhr.send(f.slice(off));});}
function maximumUploadRequest(f,uploadId,onProgress){return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest(),url='/upload?name='+encodeURIComponent(f.name)+'&offset=0&total='+f.size;xhr.open('PUT',url,true);xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.setRequestHeader('X-DeckyShare-Upload-ID',uploadId);xhr.setRequestHeader('X-DeckyShare-Fast','1');xhr.setRequestHeader('X-DeckyShare-No-Resume','1');xhr.upload.onprogress=e=>onProgress(Math.min(f.size,Number(e.loaded||0)));xhr.onload=()=>{untrackUploadController(xhr);let data={};try{data=JSON.parse(xhr.responseText||'{}');}catch(e){}resolve({status:xhr.status,ok:xhr.status>=200&&xhr.status<300,data,text:xhr.responseText||''});};xhr.onerror=()=>{untrackUploadController(xhr);reject(new Error('Connection interrupted — restart required in Maximum Speed mode'));};xhr.onabort=()=>{untrackUploadController(xhr);reject(cancelledError());};trackUploadController(xhr);xhr.send(f);});}
function parallelUploadRequest(f,uploadId,lane,lanes,start,end,off,onProgress){return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest(),url='/upload?name='+encodeURIComponent(f.name)+'&offset='+off+'&total='+f.size+'&lane='+lane+'&lanes='+lanes;xhr.open('PUT',url,true);xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.setRequestHeader('X-DeckyShare-Upload-ID',uploadId);xhr.setRequestHeader('X-DeckyShare-Fast','1');xhr.setRequestHeader('X-DeckyShare-Parallel','1');xhr.upload.onprogress=e=>onProgress(Math.min(end-start,(off-start)+Number(e.loaded||0)));xhr.onload=()=>{untrackUploadController(xhr);let data={};try{data=JSON.parse(xhr.responseText||'{}');}catch(e){}resolve({status:xhr.status,ok:xhr.status>=200&&xhr.status<300,data,text:xhr.responseText||''});};xhr.onerror=()=>{untrackUploadController(xhr);reject(new Error('Parallel lane interrupted'));};xhr.onabort=()=>{untrackUploadController(xhr);const e=new Error('Upload paused');e.name='AbortError';reject(e);};trackUploadController(xhr);xhr.send(f.slice(off,end));});}
async function uploadOneMaximum(f,onProgress){const uploadId=newUploadId();document.getElementById('diag').textContent='Maximum Speed • one raw continuous stream • no checkpoints';try{const r=await maximumUploadRequest(f,uploadId,onProgress);if(uploadControl.cancelled)throw cancelledError();const j=r.data||{};if(!r.ok)throw new Error(j.error||r.text||('Upload error '+r.status));onProgress(f.size);return j.name||f.name;}catch(e){await cancelPartial(f.name,uploadId);if(uploadControl.cancelled||e.cancelled)throw cancelledError();throw e;}}
async function uploadOneParallel(f,onProgress,onRetry){const uploadId=newUploadId(),lanes=3,bounds=Array.from({length:lanes},(_,i)=>[Math.floor(f.size*i/lanes),Math.floor(f.size*(i+1)/lanes)]),committed=Array(lanes).fill(0),visible=Array(lanes).fill(0);let lastName=f.name;document.getElementById('diag').textContent='Turbo mode • 3 parallel native streams • resumable Deck ranges';const report=()=>onProgress(visible.reduce((a,b)=>a+b,0));const syncStatus=async()=>{const s=await uploadStatus(f,uploadId);if(Array.isArray(s.parts))for(let i=0;i<lanes;i++){committed[i]=Number(s.parts[i]||0);visible[i]=committed[i];}report();return s;};const runLane=async lane=>{const [start,end]=bounds[lane];let retries=0;while(start+committed[lane]<end){await waitWhilePaused();const off=start+committed[lane];try{const r=await parallelUploadRequest(f,uploadId,lane,lanes,start,end,off,n=>{visible[lane]=n;report();});if(uploadControl.cancelled)throw cancelledError();const j=r.data||{};if(r.status===409){committed[lane]=Number(j.lane_received||0);visible[lane]=committed[lane];continue;}if(!r.ok)throw new Error(j.error||r.text||('Upload error '+r.status));committed[lane]=Number(j.lane_received||end-start);visible[lane]=committed[lane];lastName=j.name||lastName;retries=0;report();}catch(e){if(uploadControl.cancelled)throw cancelledError();const s=await syncStatus();if(s.complete){lastName=s.name||lastName;return;}if(uploadControl.paused){onRetry('Paused at Deck range checkpoint');await waitWhilePaused();continue;}retries++;if(retries>5)throw e;onRetry('Turbo lane '+(lane+1)+' reconnecting ('+retries+'/5)');await new Promise(r=>setTimeout(r,350*retries));}}};try{await Promise.all(Array.from({length:lanes},(_,i)=>runLane(i)));const final=await uploadStatus(f,uploadId);lastName=final.name||lastName;onProgress(f.size);return lastName;}catch(e){if(uploadControl.cancelled){await cancelPartial(f.name,uploadId);throw cancelledError();}throw e;}}
async function uploadOneFast(f,onProgress,onRetry){const uploadId=newUploadId();let off=0,lastName=f.name,retries=0,first=true;document.getElementById('diag').textContent='Fast mode • native continuous stream • resumable Deck checkpoint';while(first||off<f.size){first=false;await waitWhilePaused();try{const r=await fastUploadRequest(f,off,uploadId,onProgress);if(uploadControl.cancelled){await cancelPartial(f.name,uploadId);throw cancelledError();}const j=r.data||{};if(r.status===409){off=Number(j.received||0);onProgress(off);onRetry('Resuming from Deck checkpoint '+fmt(off));continue;}if(!r.ok)throw new Error(j.error||r.text||('Upload error '+r.status));off=Number(j.received||0);lastName=j.name||lastName;retries=0;onProgress(off);if(j.complete)break;}catch(e){uploadControl.controller=null;if(uploadControl.cancelled){await cancelPartial(f.name,uploadId);throw cancelledError();}const checkpoint=await stableCheckpoint(f,uploadId,off);off=Number(checkpoint.received||0);onProgress(off);if(checkpoint.complete){lastName=checkpoint.name||lastName;break;}if(uploadControl.paused){onRetry('Paused at Deck checkpoint '+fmt(off));await waitWhilePaused();onRetry('Resuming from '+fmt(off));continue;}retries++;if(retries>5)throw e;onRetry('Connection interrupted — resuming '+fmt(off)+' ('+retries+'/5)');await new Promise(r=>setTimeout(r,500*retries));}}return lastName;}
async function uploadOneReliable(f,onProgress,onRetry){const uploadId=newUploadId();let chunk=4*1024*1024,off=0,lastName=f.name,retries=0,first=true;document.getElementById('diag').textContent='Reliable compatibility mode • verified 4 MB chunks';while(first||off<f.size){first=false;let controller=null;try{await waitWhilePaused();const current=await prepareUploadChunk(f,off,chunk);controller=new AbortController();trackUploadController(controller);const r=await fetch('/upload?name='+encodeURIComponent(f.name)+'&offset='+off+'&total='+f.size,{method:'PUT',headers:{'Content-Type':'application/octet-stream','X-DeckyShare-CRC32':current.sum,'X-DeckyShare-Upload-ID':uploadId},body:current.blob,signal:controller.signal});untrackUploadController(controller);if(uploadControl.cancelled){await cancelPartial(f.name,uploadId);throw cancelledError();}const j=await r.json();if(r.status===409){off=Number(j.received||0);onProgress(off);continue;}if(!r.ok)throw new Error(j.error||('Upload error '+r.status));off=Number(j.received||0);lastName=j.name||lastName;retries=0;onProgress(off);if(j.complete)break;}catch(e){if(controller)untrackUploadController(controller);if(uploadControl.cancelled){await cancelPartial(f.name,uploadId);throw cancelledError();}if(uploadControl.paused){await waitWhilePaused();continue;}retries++;if(retries>3)throw e;onRetry('Reliable retry '+retries+'/3');await new Promise(r=>setTimeout(r,600*retries));}}return lastName;}
async function uploadOne(f,onProgress,onRetry,noResume){if(noResume&&typeof XMLHttpRequest!=='undefined')return uploadOneMaximum(f,onProgress);if(typeof XMLHttpRequest==='undefined')return uploadOneReliable(f,onProgress,onRetry);if(f.size>=64*1024*1024)return uploadOneParallel(f,onProgress,onRetry);return uploadOneFast(f,onProgress,onRetry);}
document.getElementById('download').addEventListener('click',async(e)=>{
  if(!e.currentTarget.href)return;
  await requestTransferWakeLock();
  setAwakeText('Download started. Keep this page open until your browser reports completion.');
});

document.getElementById('pause').onclick=()=>{if(!uploadControl.running||uploadControl.noResume)return;uploadControl.paused=!uploadControl.paused;if(uploadControl.paused)abortActiveUploads();document.getElementById('pause').textContent=uploadControl.paused?'Resume':'Pause';document.getElementById('uptext').textContent=uploadControl.paused?'Pausing at Deck checkpoint…':'Resuming…';};
document.getElementById('cancel').onclick=()=>{if(!uploadControl.running)return;uploadControl.cancelled=true;uploadControl.paused=false;abortActiveUploads();document.getElementById('pause').textContent='Pause';document.getElementById('uptext').textContent='Cancelling now…';};
"""

_UI_JS = r"""
const $=id=>document.getElementById(id);
let picked=[],lastSelected=null,connOk=true,lastShared=null;
function sizeText(n){return fmt(n);}
function plural(n,w){return n+' '+w+(n===1?'':'s');}
let currentTab='send';
function setTab(name){currentTab=name;for(const t of ['send','get','text']){$('tab-'+t).setAttribute('aria-selected',t===name);$('panel-'+t).classList.toggle('hidden',t!==name);}if(name==='text')markTextsSeen();}
$('tab-send').onclick=()=>setTab('send');
$('tab-get').onclick=()=>setTab('get');
$('tab-text').onclick=()=>setTab('text');
let texts=[],textsRev=null,textSeen=null,textsStarted=false;
function timeAgo(ts){const s=Math.max(0,Date.now()/1000-Number(ts||0));if(s<60)return 'just now';if(s<3600)return Math.round(s/60)+' min ago';if(s<86400)return Math.round(s/3600)+' h ago';return Math.round(s/86400)+' d ago';}
function linkify(t){return escapeHtml(t).replace(/https?:\/\/[^\s<]+/g,u=>`<a href="${u}" target="_blank" rel="noopener noreferrer">${u}</a>`);}
function markTextsSeen(){textSeen=texts.length?texts[0].id:null;$('textbadge').classList.add('hidden');}
function renderTexts(){
  $('tcount').textContent=texts.length?plural(texts.length,'item'):'';
  if(!texts.length){$('tlist').innerHTML='<div class="empty"><b>No text yet</b>Send a link or a note to your Deck, or type one in DeckyShare on the Deck. It shows up here.</div>';return;}
  $('tlist').innerHTML='<div class="list">'+texts.map(t=>`<div class="titem"><div class="ttext">${linkify(t.text)}</div><div class="tfoot"><span class="tmeta">${t.from==='Deck'?'From Deck':'From '+escapeHtml(t.from||'device')} · ${escapeHtml(timeAgo(t.at))}</span>${t.link?`<a class="chip" href="${escapeHtml(t.text)}" target="_blank" rel="noopener noreferrer">Open</a>`:''}<button class="chip" data-copy="${t.id}">Copy</button><button class="chip del" data-del="${t.id}" aria-label="Delete"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8ea2b8" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div></div>`).join('')+'</div>';
}
function applyTexts(list,rev){
  texts=Array.isArray(list)?list:[];textsRev=rev;renderTexts();
  const top=texts[0];
  if(!textsStarted){textsStarted=true;textSeen=top?top.id:null;return;}
  if(top&&top.id!==textSeen){if(currentTab==='text')markTextsSeen();else if(top.from==='Deck')$('textbadge').classList.remove('hidden');}
}
async function copyText(text){
  try{if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(text);return true;}}catch(e){}
  const ta=document.createElement('textarea');ta.value=text;ta.setAttribute('readonly','');ta.style.cssText='position:fixed;top:0;left:0;opacity:0;font-size:16px';document.body.appendChild(ta);
  const range=document.createRange();range.selectNodeContents(ta);const sel=window.getSelection();sel.removeAllRanges();sel.addRange(range);ta.select();ta.setSelectionRange(0,text.length);
  let ok=false;try{ok=document.execCommand('copy');}catch(e){ok=false;}
  document.body.removeChild(ta);sel.removeAllRanges();return ok;
}
$('tlist').addEventListener('click',async e=>{
  const c=e.target.closest('button[data-copy]'),d=e.target.closest('button[data-del]');
  if(c){const t=texts.find(x=>x.id===c.dataset.copy);if(!t)return;const ok=await copyText(t.text);c.textContent=ok?'Copied ✓':'Copy failed';c.classList.toggle('ok',ok);setTimeout(()=>{c.textContent='Copy';c.classList.remove('ok');},1800);}
  if(d){try{const r=await(await api('/api/text-delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:d.dataset.del})})).json();applyTexts(r.texts,r.texts_rev);}catch(err){}}
});
const tinput=$('tinput');
tinput.addEventListener('input',()=>{$('tsend').disabled=!tinput.value.trim();});
if(navigator.clipboard&&navigator.clipboard.readText&&window.isSecureContext)$('tpaste').classList.remove('hidden');
$('tpaste').onclick=async()=>{try{tinput.value=await navigator.clipboard.readText();tinput.dispatchEvent(new Event('input'));}catch(e){$('tnote').textContent='Paste is blocked here: long-press the box and choose Paste.';}};
$('tsend').onclick=async()=>{
  const text=tinput.value.trim();if(!text)return;$('tsend').disabled=true;$('tnote').textContent='';
  try{const res=await fetch('/api/text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});const r=await res.json();if(!res.ok)throw new Error(r.error||('Error '+res.status));tinput.value='';applyTexts(r.texts,r.texts_rev);markTextsSeen();$('tnote').textContent='Sent to your Deck ✓';setTimeout(()=>{$('tnote').textContent='';},2500);}
  catch(e){$('tnote').textContent='Could not send: '+e.message;$('tsend').disabled=false;}
};
function renderPicked(){
  const wrap=$('pickedwrap'),list=$('picked'),btn=$('upload');
  const busy=uploadControl.running;btn.classList.toggle('hidden',busy);$('drop').classList.toggle('hidden',busy);
  if(busy||!picked.length){wrap.classList.add('hidden');list.innerHTML='';btn.disabled=true;$('uploadlabel').textContent='Send to Deck';return;}
  wrap.classList.remove('hidden');
  $('pickedsum').textContent=plural(picked.length,'file')+' · '+sizeText(picked.reduce((n,f)=>n+f.size,0));
  list.innerHTML=picked.map((f,i)=>`<div class="item"><div class="meta"><span class="name">${escapeHtml(f.name)}</span><span class="sub">${escapeHtml(sizeText(f.size))}</span></div><button class="x" data-i="${i}" aria-label="Remove ${escapeHtml(f.name)}"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8ea2b8" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>`).join('');
  btn.disabled=uploadControl.running;
  $('uploadlabel').textContent=picked.length===1?'Send to Deck':'Send '+picked.length+' files to Deck';
}
$('picked').addEventListener('click',e=>{const b=e.target.closest('button[data-i]');if(!b||uploadControl.running)return;picked.splice(Number(b.dataset.i),1);renderPicked();});
function addFiles(list){const have=new Set(picked.map(f=>f.name+'|'+f.size));for(const f of Array.from(list||[])){const k=f.name+'|'+f.size;if(!have.has(k)){picked.push(f);have.add(k);}}renderPicked();}
$('file').addEventListener('change',()=>{const input=$('file');addFiles(input.files);input.value='';});
const drop=$('drop');
['dragenter','dragover'].forEach(t=>drop.addEventListener(t,e=>{e.preventDefault();drop.classList.add('over');}));
['dragleave','drop'].forEach(t=>drop.addEventListener(t,e=>{e.preventDefault();drop.classList.remove('over');}));
drop.addEventListener('drop',e=>{if(e.dataTransfer&&e.dataTransfer.files)addFiles(e.dataTransfer.files);});

function renderQueue(){const q=$('queue');if(queueState.length<2){q.classList.add('hidden');q.innerHTML='';return;}q.classList.remove('hidden');q.innerHTML=queueState.map(x=>{const s=String(x.status||''),cls=s==='Done'?'ok':(s==='Failed'?'bad':(s.startsWith('Uploading')?'on':''));const label=s.startsWith('Uploading')?'Sending':s;return `<div class="item"><div class="meta"><span class="name">${escapeHtml(x.name)}</span><span class="sub">${escapeHtml(sizeText(x.size||0))}</span></div><span class="state ${cls}">${escapeHtml(label)}</span></div>`;}).join('');}

function duration(s){if(!isFinite(s)||s<0)return '–';s=Math.round(s);if(s<60)return s+' s';const m=Math.floor(s/60),r=s%60;if(m<60)return m+' min'+(r?' '+r+' s':'');return Math.floor(m/60)+' h '+(m%60)+' min';}
let meter={samples:[],last:0,lastAt:0,total:0};
function meterReset(total){meter={samples:[[performance.now(),0]],last:0,lastAt:performance.now(),total};}
function meterAdd(done){const now=performance.now();if(done!==meter.last){meter.last=done;meter.lastAt=now;}meter.samples.push([now,done]);while(meter.samples.length>2&&now-meter.samples[1][0]>3000)meter.samples.shift();}
function meterRender(){
  if(!uploadControl.running)return;
  const now=performance.now(),idle=(now-meter.lastAt)/1000;
  let speed=0;const s0=meter.samples[0];if(s0&&now>s0[0])speed=Math.max(0,(meter.last-s0[1])/((now-s0[0])/1000));
  const stalled=idle>3&&!uploadControl.paused;
  if(stalled)speed=0;
  $('xspeed').textContent=uploadControl.paused?'Paused':fmt(speed)+'/s';
  $('xeta').textContent=(speed>1&&!stalled)?duration((meter.total-meter.last)/speed):'–';
  $('xstall').classList.toggle('hidden',!stalled);
  if(stalled)$('xstallfor').textContent='No data for '+Math.round(idle)+' s.';
}
setInterval(meterRender,1000);

function showXfer(state){
  const card=$('xfer');card.classList.remove('hidden');card.classList.toggle('done',state==='done');
  $('xactions').classList.toggle('hidden',state!=='active');
}
function hideXfer(){$('xfer').classList.add('hidden');$('xfer').classList.remove('done');$('xstall').classList.add('hidden');}

async function refresh(){
  try{
    const s=await(await api('/api/status')).json();
    if(!connOk){connOk=true;$('conn').classList.remove('off');$('conn').lastElementChild.textContent='Connected to Steam Deck';}
    const sel=s.selected,a=$('download');
    const key=sel?sel.name+'|'+sel.size:null;
    if(key!==lastSelected){
      lastSelected=key;
      if(sel){$('selected').innerHTML=`<div class="file-card"><div class="file-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#9aabbd" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg></div><div class="meta" style="flex:1;min-width:0"><div class="xfer-name">${escapeHtml(sel.name)}</div><div class="xfer-size">${escapeHtml(sel.size_human)} · ready on your Deck</div></div></div>`;a.classList.remove('hidden');a.href='/download';}
      else{$('selected').innerHTML='<div class="empty"><b>Nothing shared yet</b>Pick a file in DeckyShare on your Steam Deck. It will show up here.</div>';a.classList.add('hidden');a.removeAttribute('href');}
    }
    const shared=Array.isArray(s.shared)?s.shared:[];
    const skey=shared.map(x=>x.name+'|'+x.size).join('/');
    if(skey!==lastShared){
      lastShared=skey;
      $('gallerywrap').classList.toggle('hidden',!shared.length);
      $('gallerycount').textContent=shared.length?plural(shared.length,'file'):'';
      const bust=Date.now();
      $('gallery').innerHTML=shared.map(x=>x.image
        ?`<div class="shot"><img src="/shared?i=${x.i}&v=${bust}" alt="${escapeHtml(x.name)}" loading="lazy"><a href="/download?i=${x.i}" download="${escapeHtml(x.name)}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#c9d6e3" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v12M7 11l5 5 5-5"/></svg>Download</a></div>`
        :`<div class="shot"><div class="item"><div class="meta"><span class="name">${escapeHtml(x.name)}</span><span class="sub">${escapeHtml(x.size_human)}</span></div></div><a href="/download?i=${x.i}">Download</a></div>`).join('');
      if(shared.length&&!sel)$('selected').innerHTML='';
      else if(!sel)$('selected').innerHTML='<div class="empty"><b>Nothing shared yet</b>Pick a file in DeckyShare on your Steam Deck. It will show up here.</div>';
    }
    $('getbadge').textContent=shared.length>1?String(shared.length):'1';
    $('getbadge').classList.toggle('hidden',!sel&&!shared.length);
    if(s.texts_rev!==undefined&&s.texts_rev!==textsRev)applyTexts(s.texts,s.texts_rev);
    const downs=(s.transfers||[]).filter(x=>x.direction!=='upload');
    $('transferswrap').classList.toggle('hidden',!downs.length);
    $('transfers').innerHTML=downs.map(x=>`<div class="item"><div class="meta"><span class="name">${escapeHtml(x.name)}</span><span class="sub">${Number(x.percent||0).toFixed(0)}% · ${x.stalled?'<b style="color:#ffb454">stalled '+Math.round(x.stalled_for||0)+' s</b>':escapeHtml(fmt(x.speed||0)+'/s')}${x.eta?' · '+escapeHtml(duration(x.eta))+' left':''}</span><div class="bar" style="height:6px;margin-top:6px"><div class="fill" style="width:${Math.min(100,x.percent||0)}%"></div></div></div></div>`).join('');
  }catch(e){
    if(connOk){connOk=false;$('conn').classList.add('off');$('conn').lastElementChild.textContent='Reconnecting to Steam Deck…';}
  }
}

document.getElementById('upload').onclick=async()=>{
  const input=document.getElementById('file'),files=picked.slice(),u=document.getElementById('uptext'),b=document.getElementById('upbar'),btn=document.getElementById('upload'),pause=document.getElementById('pause'),cancel=document.getElementById('cancel'),maxspeed=document.getElementById('maxspeed');
  if(!files.length||uploadControl.running)return;
  const noResume=!!maxspeed.checked,total=files.reduce((n,f)=>n+f.size,0);let finished=0,current=-1;
  queueState=files.map(f=>({name:f.name,size:f.size,status:'Waiting'}));renderQueue();
  uploadControl={running:true,paused:false,cancelled:false,controller:null,controllers:[],noResume};
  meterReset(total);showXfer('active');renderPicked();
  $('xlabel').textContent='Sending to Deck';$('xmode').textContent=noResume?'Max speed':(files.some(f=>f.size>=64*1024*1024)?'Turbo':'Fast');
  $('xpct').textContent='0';b.style.width='0%';u.textContent='';
  await requestTransferWakeLock();
  btn.disabled=true;maxspeed.disabled=true;pause.disabled=noResume;pause.classList.toggle('hidden',noResume);$('xactions').classList.toggle('one',noResume);cancel.disabled=false;
  try{
    for(let i=0;i<files.length;i++){
      current=i;if(uploadControl.cancelled)throw cancelledError();
      const f=files[i];
      $('xlabel').textContent=files.length>1?`Sending to Deck · ${i+1} of ${files.length}`:'Sending to Deck';
      $('xname').textContent=f.name;
      setQueueStatus(i,noResume?'Uploading • Maximum Speed':(f.size>=64*1024*1024?'Uploading • Turbo mode':'Uploading • Fast mode'));
      await uploadOne(f,done=>{
        const overall=total?((finished+done)*100/total):100;
        meterAdd(finished+done);
        $('xpct').textContent=String(Math.min(100,Math.floor(overall)));
        $('xsize').textContent=fmt(done)+' of '+fmt(f.size)+(files.length>1?' · '+fmt(finished+done)+' of '+fmt(total)+' total':'');
        b.style.width=Math.min(100,overall)+'%';
      },s=>{u.textContent=s;},noResume);
      finished+=f.size;setQueueStatus(i,'Done');
    }
    meterAdd(total);showXfer('done');
    $('xlabel').textContent='Sent to Deck';$('xpct').textContent='100';b.style.width='100%';
    $('xname').textContent=files.length===1?files[0].name:plural(files.length,'file');$('xsize').textContent=fmt(total)+' · saved in Downloads/DeckShare';
    $('xspeed').textContent='Done';$('xeta').textContent='–';u.textContent='';
    picked=[];renderPicked();
    setTimeout(()=>{if(!uploadControl.running){hideXfer();input.value='';queueState=[];renderQueue();}},4000);
  }catch(e){
    if(e.cancelled){
      u.textContent='Transfer cancelled';b.style.width='0%';input.value='';queueState=[];renderQueue();
      const diag=document.getElementById('diag');if(diag)diag.textContent='';
      setTimeout(()=>{if(!uploadControl.running){u.textContent='';hideXfer();}},1500);
    }else{
      if(current>=0)setQueueStatus(current,'Failed');
      $('xlabel').textContent='Transfer failed';u.textContent='Upload failed: '+e.message+'. Your files are still selected, so you can try again.';
      $('xactions').classList.add('hidden');
    }
  }finally{
    uploadControl.controller=null;uploadControl.controllers=[];uploadControl.running=false;uploadControl.paused=false;uploadControl.noResume=false;
    await releaseTransferWakeLock();
    maxspeed.disabled=false;pause.disabled=true;cancel.disabled=true;pause.textContent='Pause';pause.classList.remove('hidden');$('xactions').classList.remove('one');
    renderPicked();$('xstall').classList.add('hidden');
  }
};
renderPicked();refresh();setInterval(refresh,1000);setInterval(()=>{if(currentTab==='text')renderTexts();},30000);
"""


def html_page(address):
    esc = html.escape(address)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="theme-color" content="#0b1118">'
        "<title>DeckyShare</title><style>" + _CSS + "</style></head><body>"
        + _BODY.replace("__ADDRESS__", esc)
        + "<script>\n" + _CORE_JS + _UI_JS + "</script></body></html>"
    )


_PAIR_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connect to DeckyShare</title>
<style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px 16px;
background:#0b1118;color:#e8eef5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
.card{width:100%;max-width:400px;background:#131c27;border:1px solid #22303f;border-radius:20px;padding:28px 24px;
display:flex;flex-direction:column;gap:16px}
.brand{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:800}
.logo{width:36px;height:36px;border-radius:11px;background:#1a9fff;display:flex;align-items:center;justify-content:center}
h1{margin:0;font-size:22px}
p{margin:0;color:#9aabbd;font-size:15px;line-height:1.45}
label{font-size:13px;font-weight:700;color:#c9d6e3}
input{width:100%;min-height:64px;border-radius:14px;border:2px solid #2c4057;background:#0f1720;color:#fff;
font-size:34px;font-weight:800;letter-spacing:10px;text-align:center;font-family:ui-monospace,Menlo,Consolas,monospace}
input:focus{outline:none;border-color:#1a9fff}
button{min-height:52px;border:0;border-radius:14px;background:#1a9fff;color:#06121f;font-size:17px;font-weight:800;cursor:pointer}
button:disabled{opacity:.6;cursor:default}
.err{min-height:20px;color:#ff9a9a;font-size:14px;font-weight:600}
.hint{font-size:13px;color:#6f8399}
</style></head>
<body><main class="card">
<div class="brand"><div class="logo"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06121f" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 7h11l-3-3M17 17H6l3 3"/></svg></div>DeckyShare</div>
<h1>Enter the code from your Steam Deck</h1>
<p>Open DeckyShare on the Deck. The 6-digit code is shown in the <b>Connect</b> card, under <b>Computer</b>.</p>
<form id="f" style="display:flex;flex-direction:column;gap:10px">
<label for="code">Code</label>
<input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="7" placeholder="000000" autofocus required>
<div id="err" class="err" role="alert"></div>
<button id="go" type="submit">Connect</button>
</form>
<div class="hint">Phones can scan the QR code on the Deck instead.</div>
</main>
<script>
const f=document.getElementById('f'),input=document.getElementById('code'),err=document.getElementById('err'),go=document.getElementById('go');
input.addEventListener('input',()=>{input.value=input.value.replace(/[^0-9]/g,'').slice(0,6);err.textContent='';});
f.addEventListener('submit',async e=>{
  e.preventDefault();
  if(input.value.length!==6){err.textContent='Enter all 6 digits.';return;}
  go.disabled=true;go.textContent='Connecting…';
  try{
    const r=await fetch('/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:input.value}),credentials:'same-origin'});
    const j=await r.json().catch(()=>({}));
    if(r.ok&&j.ok){location.replace(j.redirect||'/');return;}
    err.textContent=j.error||('Could not connect ('+r.status+')');
  }catch(x){err.textContent='Could not reach the Deck. Are both on the same Wi-Fi?';}
  go.disabled=false;go.textContent='Connect';input.select();
});
</script>
</body></html>
"""


def pair_page_html():
    return _PAIR_PAGE
