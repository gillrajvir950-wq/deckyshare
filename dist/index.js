// @ts-nocheck
const React = window.SP_REACT || window.React;
const h = React.createElement;
const { forwardRef, useEffect, useMemo, useRef, useState } = React;
const DeckyUI = window.DFL || {};
const BaseDialogButton = DeckyUI.DialogButton || "button";
const Focusable = DeckyUI.Focusable || "div";
const BaseTextField = DeckyUI.TextField || "input";
const CONTROLLER_FOCUS_STYLE = {
    outline: "none",
    outlineOffset: 0,
    border: "1px solid #8fd0ff",
    boxShadow: "0 0 0 2px rgba(102,192,244,.28), 0 0 14px rgba(26,159,255,.28)",
    filter: "brightness(1.22)",
    position: "relative",
    zIndex: 1,
    transform: "none"
};
const CARD_FOCUS_STYLE = {
    border: "1px solid #8fd0ff",
    background: "linear-gradient(135deg,rgba(56,104,150,.92),rgba(30,58,90,.94))",
    boxShadow: "0 0 0 2px rgba(102,192,244,.30), 0 6px 20px rgba(26,159,255,.28)"
};
const DialogButton = forwardRef(function DeckyShareDialogButton(props, ref) {
    const [focused, setFocused] = useState(false);
    const { style, onFocus, onBlur, className, plainFocus, ...rest } = props || {};
    const focus = e => { setFocused(true); if (typeof onFocus === "function")
        onFocus(e); };
    const blur = e => { setFocused(false); if (typeof onBlur === "function")
        onBlur(e); };
    const shared = { ...rest, ref, className: `deckyshare-action${className ? ` ${className}` : ""}`, style: { ...style, ...(focused && !plainFocus ? CONTROLLER_FOCUS_STYLE : {}) }, onFocus: focus, onBlur: blur };
    if (BaseDialogButton !== "button") {
        shared.noFocusRing = true;
    }
    return h(BaseDialogButton, shared);
});
function TextField(props) {
    // The Steam keyboard can change the text box without React noticing (for
    // example its Paste key). React would then put the old text back on the next
    // render, so listen to the box itself and report every change.
    const [focused, setFocused] = useState(false);
    const elRef = useRef(null), propsRef = useRef(props);
    propsRef.current = props;
    const { style, onFocus, onBlur, className, value, uncontrolled, inputRef, debugLog, ...rest } = props || {};
    function bind(el) {
        if (!el || elRef.current === el || typeof el.addEventListener !== "function")
            return;
        elRef.current = el;
        if (inputRef)
            inputRef.current = el;
        const sync = () => {
            const p = propsRef.current;
            if (typeof p.onChange !== "function")
                return;
            if (p.uncontrolled || String(p.value == null ? "" : p.value) !== el.value)
                p.onChange({ target: el, currentTarget: el });
        };
        ["input", "change", "keyup", "compositionend"].forEach(t => el.addEventListener(t, sync));
        el.addEventListener("paste", () => setTimeout(sync, 0));
        if (typeof propsRef.current.debugLog === "function") {
            const log = (...a) => { try {
                propsRef.current.debugLog(a.join(" "));
            }
            catch (e) { } };
            el.addEventListener("keydown", e => log("keydown", JSON.stringify(e.key), e.ctrlKey ? "ctrl" : "", "len", el.value.length));
            el.addEventListener("beforeinput", e => log("beforeinput", e.inputType, "data", e.data == null ? "-" : String(e.data).length));
            el.addEventListener("input", e => log("input", e.inputType || "-", "len", el.value.length));
            el.addEventListener("paste", e => { let n = "?"; try {
                n = String(e.clipboardData && e.clipboardData.getData("text").length);
            }
            catch (_e) { } log("paste clip", n); setTimeout(() => log("after paste len", el.value.length), 50); });
            let last = el.value;
            setInterval(() => { if (el.value !== last) {
                log("value now len", el.value.length, "(was", last.length + ")");
                last = el.value;
            } }, 250);
        }
    }
    const fieldProps = { ...rest, className: `deckyshare-text-field${className ? ` ${className}` : ""}`, style: { ...style, ...(focused ? CONTROLLER_FOCUS_STYLE : {}) },
        onFocus: e => { bind(e && e.target); setFocused(true); if (typeof onFocus === "function")
            onFocus(e); },
        onBlur: e => { setFocused(false); if (typeof onBlur === "function")
            onBlur(e); } };
    if (!uncontrolled)
        fieldProps.value = value;
    return h(BaseTextField, fieldProps);
}
const NOTIFY_KEY = "deckyshare.notifications";
const NOTIFY_TTL = 4000;
const notifySeen = new Map();
let receivedBatch = [];
let receivedBatchTimer = null;
function fmt(n) {
    if (!Number.isFinite(n))
        return "0 B";
    if (n >= 1073741824)
        return (n / 1073741824).toFixed(1) + " GB";
    if (n >= 1048576)
        return (n / 1048576).toFixed(1) + " MB";
    if (n >= 1024)
        return (n / 1024).toFixed(1) + " KB";
    return Math.round(n) + " B";
}
function notificationsEnabled() { try {
    return window.localStorage.getItem(NOTIFY_KEY) !== "off";
}
catch (e) {
    return true;
} }
function saveNotificationsEnabled(v) { try {
    window.localStorage.setItem(NOTIFY_KEY, v ? "on" : "off");
}
catch (e) { } }
function unwrap(item) { return item && item.result || item && item.data || item || {}; }
function notifyKey(type, item) { const p = unwrap(item); return `${type}:${p.path || p.id || p.name || "unknown"}`; }
function shouldNotify(type, item) {
    if (!notificationsEnabled())
        return false;
    const now = Date.now(), key = notifyKey(type, item), prev = notifySeen.get(key);
    for (const [k, t] of notifySeen) {
        if (now - t >= NOTIFY_TTL)
            notifySeen.delete(k);
    }
    if (prev != null && now - prev < NOTIFY_TTL)
        return false;
    notifySeen.set(key, now);
    return true;
}
function toast(api, body) {
    try {
        if (api && api.toaster && typeof api.toaster.toast === "function")
            api.toaster.toast({ title: "DeckyShare", body });
    }
    catch (e) {
        console.error("[DeckyShare] toast failed", e);
    }
}
function flushReceivedBatch(api) {
    const batch = receivedBatch.splice(0);
    receivedBatchTimer = null;
    if (!batch.length || !notificationsEnabled())
        return;
    if (batch.length === 1) {
        const p = batch[0];
        toast(api, `Received: ${p.name || "file"}\nSaved to: ${p.path || "Downloads/DeckShare"}`);
        return;
    }
    const names = batch.slice(0, 3).map(x => x.name || "file").join(", ");
    const more = batch.length > 3 ? ` +${batch.length - 3} more` : "";
    toast(api, `Received ${batch.length} files\n${names}${more}`);
}
function queueReceivedToast(api, item) {
    if (!item || !shouldNotify("received", item))
        return;
    const p = unwrap(item);
    if (!receivedBatch.some(x => (x.path || x.name) === (p.path || p.name)))
        receivedBatch.push(p);
    if (receivedBatchTimer)
        clearTimeout(receivedBatchTimer);
    receivedBatchTimer = setTimeout(() => flushReceivedBatch(api), 900);
}
function showTransferResult(api, t) {
    if (!t || !t.id)
        return;
    if (t.status === "failed" && shouldNotify("failed", t))
        toast(api, `Transfer failed: ${t.name || "file"}`);
    else if (t.status === "complete" && t.direction === "download" && shouldNotify("sent", t))
        toast(api, `Sent to phone / PC: ${t.name || "file"}`);
}
function withTimeout(promise, ms, label) {
    return Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timed out after ${Math.ceil(ms / 1000)}s`)), ms))]);
}
function dirname(p) {
    if (!p)
        return null;
    const i = p.lastIndexOf("/");
    return i > 0 ? p.slice(0, i) : "/";
}
const ICON_PATHS = {
    swap: ["M7 7h11l-3-3", "M17 17H6l3 3"],
    scan: ["M4 8V5a1 1 0 0 1 1-1h3", "M16 4h3a1 1 0 0 1 1 1v3", "M20 16v3a1 1 0 0 1-1 1h-3", "M8 20H5a1 1 0 0 1-1-1v-3", "M8 12h8"],
    send: ["M12 15V4", "M7 9l5-5 5 5", "M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"],
    inbox: ["M12 4v11", "M7 10l5 5 5-5", "M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"],
    wifi: ["M2 8.5a15 15 0 0 1 20 0", "M5 12a10.5 10.5 0 0 1 14 0", "M8.5 15.5a5.5 5.5 0 0 1 7 0", "M12 19h.01"],
    bell: ["M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9", "M10.3 21a1.94 1.94 0 0 0 3.4 0"],
    update: ["M21 12a9 9 0 1 1-3-6.7L21 8", "M21 3v5h-5"],
    heart: ["M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7z"],
    folder: ["M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"],
    home: ["M3 11l9-8 9 8", "M5 10v10h14V10"],
    drive: ["M6 3h9l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z", "M9 7v3", "M12 7v3", "M15 7v3"],
    image: ["M4 5h16v14H4z", "M4 16l5-5 4 4 3-3 4 4", "M15.5 8.5h.01"],
    video: ["M3 6h12v12H3z", "M15 10l6-3v10l-6-3"],
    archive: ["M4 4h16v4H4z", "M5 8v12h14V8", "M10 12h4"],
    disc: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18", "M12 10a2 2 0 1 0 0 4a2 2 0 1 0 0-4"],
    doc: ["M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z", "M14 3v5h5"],
    text: ["M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z", "M14 3v5h5", "M9 13h6", "M9 17h4"],
    monitor: ["M3 4h18v12H3z", "M8 20h8", "M12 16v4"],
    settings: ["M12 15a3 3 0 1 0 0-6a3 3 0 1 0 0 6", "M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"],
    qr: ["M4 4h6v6H4z", "M14 4h6v6h-6z", "M4 14h6v6H4z", "M14 14h2v2h-2z", "M18 14h2", "M14 18h2", "M18 18h2v2h-2z"],
    check: ["M5 12l5 5 10-10"],
    clipboard: ["M9 4h6v3H9z", "M9 5H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1h-3", "M9 12h6", "M9 16h4"],
    film: ["M4 4h16v16H4z", "M8 4v16", "M16 4v16", "M4 8h4", "M4 12h4", "M4 16h4", "M16 8h4", "M16 12h4", "M16 16h4"],
    chevronRight: ["M9 6l6 6-6 6"],
    chevronDown: ["M6 9l6 6 6-6"]
};
function Icon({ name, size = 18, color = "currentColor", strokeWidth = 2 }) {
    const paths = ICON_PATHS[name] || ICON_PATHS.doc;
    return h("svg", { viewBox: "0 0 24 24", width: size, height: size, fill: "none", stroke: color, strokeWidth, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", style: { display: "block", flexShrink: 0 } }, paths.map((d, i) => h("path", { key: i, d })));
}
function IconTile({ name, size = 30, tone = "blue" }) {
    const tones = { blue: ["rgba(26,159,255,.14)", "#7cc4ff"], green: ["rgba(61,220,132,.13)", "#7fe3ad"], amber: ["rgba(255,180,84,.14)", "#ffc979"], pink: ["rgba(255,120,160,.14)", "#ff9dbb"], gray: ["rgba(255,255,255,.07)", "#c9d6e3"] };
    const [bg, fg] = tones[tone] || tones.blue;
    return h("div", { style: { width: size, height: size, borderRadius: Math.round(size * .3), background: bg, color: fg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 } }, h(Icon, { name, size: Math.round(size * .58) }));
}
function browseFileIconName(item) {
    if (item && item.type === "dir")
        return "folder";
    const name = String(item && item.name || "").toLowerCase();
    if (/\.(jpg|jpeg|png|gif|webp|heic)$/.test(name))
        return "image";
    if (/\.(mp4|mkv|mov|avi|webm|m4v|m2ts|ts)$/.test(name))
        return "video";
    if (/\.(zip|7z|rar)$/.test(name))
        return "archive";
    if (/\.iso$/.test(name))
        return "disc";
    if (/\.txt$/.test(name))
        return "text";
    return "doc";
}
function browseFileIcon(item, size = 15) { return h(Icon, { name: browseFileIconName(item), size }); }
function browseDate(ts) {
    const n = Number(ts || 0);
    if (!Number.isFinite(n) || n <= 0)
        return "";
    try {
        return new Date(n * 1000).toISOString().slice(0, 10);
    }
    catch (e) {
        return "";
    }
}
function browseCrumbsFor(current, roots) {
    if (!current)
        return [];
    const match = (roots || []).filter(r => current === r.path || current.startsWith(r.path + "/")).sort((a, b) => b.path.length - a.path.length)[0];
    if (!match)
        return [{ label: current, path: current }];
    const crumbs = [{ label: match.name, path: match.path }];
    let acc = match.path;
    const rest = current.slice(match.path.length).split("/").filter(Boolean);
    for (const part of rest) {
        acc = acc.replace(/\/$/, "") + "/" + part;
        crumbs.push({ label: part, path: acc });
    }
    return crumbs;
}
function browseVisibleItems(items, query, sortMode) {
    const q = String(query || "").trim().toLowerCase();
    const list = [];
    for (const it of (items || [])) {
        const name = String(it && it.name || "");
        const lower = name.toLowerCase();
        if (q && !lower.includes(q))
            continue;
        list.push({ it, lower, mtime: Number(it && it.mtime) || 0, size: Number(it && it.size) || 0 });
    }
    list.sort((a, b) => {
        if (a.it.type !== b.it.type)
            return a.it.type === "dir" ? -1 : 1;
        if (sortMode === "date" && a.mtime !== b.mtime)
            return b.mtime - a.mtime;
        if (sortMode === "size" && a.size !== b.size)
            return b.size - a.size;
        if (a.lower < b.lower)
            return -1;
        if (a.lower > b.lower)
            return 1;
        return 0;
    });
    return list.map(x => x.it);
}
function duration(sec) {
    if (!Number.isFinite(sec) || sec < 0)
        return "";
    sec = Math.round(sec);
    if (sec < 60)
        return `${sec} s`;
    const m = Math.floor(sec / 60), r = sec % 60;
    if (m < 60)
        return r ? `${m} min ${r} s` : `${m} min`;
    return `${Math.floor(m / 60)} h ${m % 60} min`;
}
function TransferHero({ transfers, onCancel, armed }) {
    if (!transfers || !transfers.length)
        return null;
    return h(Card, { style: { border: "2px solid #1a9fff", background: "linear-gradient(180deg,rgba(18,42,68,.97),rgba(12,28,46,.97))" } }, transfers.map((t, i) => {
        const up = t.direction === "upload", pct = Math.max(0, Math.min(100, Number(t.percent || 0))), stalled = !!t.stalled;
        return h("div", { key: t.id, style: { paddingTop: i ? 10 : 0, marginTop: i ? 10 : 0, borderTop: i ? "1px solid rgba(255,255,255,.07)" : "none" } }, h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, fontSize: 10, fontWeight: 800, letterSpacing: .7, textTransform: "uppercase" } }, h("span", { style: { color: stalled ? "#ffb454" : "#7cc4ff" } }, up ? "Receiving from phone / PC" : "Sending to phone / PC"), transfers.length > 1 && h("span", { style: { color: "#9aabbd" } }, `${i + 1} of ${transfers.length}`)), h("div", { style: { fontSize: 13, fontWeight: 750, marginTop: 5, wordBreak: "break-word", lineHeight: 1.25 } }, t.name), h("div", { style: { display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8, marginTop: 6 } }, h("div", { style: { fontSize: 32, fontWeight: 850, lineHeight: 1, letterSpacing: -0.5 } }, String(Math.floor(pct)), h("span", { style: { fontSize: 15, opacity: .6, marginLeft: 2 } }, "%")), h("div", { style: { fontSize: 11, opacity: .72, textAlign: "right" } }, `${fmt(t.done || 0)} / ${fmt(t.total || 0)}`)), h("div", { style: { height: 10, borderRadius: 999, background: "rgba(255,255,255,.12)", overflow: "hidden", marginTop: 8 } }, h("div", { style: { height: "100%", width: `${pct}%`, borderRadius: 999, background: stalled ? "#ffb454" : "#1a9fff", transition: "width .4s ease" } })), h("div", { style: { display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, marginTop: 7 } }, h("span", null, h("b", null, stalled ? "0 B/s" : `${fmt(t.speed)}/s`), h("span", { style: { opacity: .6 } }, " now")), h("span", { style: { opacity: .8, color: stalled ? "#ffd08a" : "inherit" } }, stalled ? `no data for ${Math.round(t.stalled_for || 0)} s` : (t.eta ? `about ${duration(t.eta)} left` : ""))), stalled && h("div", { style: { marginTop: 8, padding: "7px 9px", borderRadius: 9, background: "rgba(255,180,84,.10)", border: "1px solid rgba(255,180,84,.28)", color: "#ffd08a", fontSize: 11, lineHeight: 1.35 } }, up ? "Keep the phone's screen on with the browser open, and stay near the router." : "Keep the receiving device awake and near the router."), onCancel && t.status === "active" && h(DialogButton, { onClick: () => onCancel(t), style: { width: "100%", minHeight: 0, marginTop: 10, padding: "9px 10px", borderRadius: 10, border: "1px solid rgba(255,120,120,.38)", background: armed === t.id ? "rgba(255,90,90,.18)" : "transparent", color: "#ff9a9a", fontSize: 13, fontWeight: 750, textAlign: "center" } }, armed === t.id ? "Press again to cancel" : "Cancel transfer"));
    }));
}
function Bar({ value }) { return h("div", { style: { height: 8, borderRadius: 6, background: "rgba(255,255,255,.12)", overflow: "hidden", marginTop: 7 } }, h("div", { style: { height: "100%", width: `${Math.max(0, Math.min(100, value || 0))}%`, background: "#66c0f4" } })); }
function Btn({ children, onClick, disabled = false }) { return h(DialogButton, { disabled, onClick, style: { width: "100%", padding: "11px 12px", margin: "5px 0", borderRadius: 11, border: "1px solid rgba(130,190,255,.20)", background: disabled ? "rgba(255,255,255,.05)" : "rgba(34,67,106,.72)", color: "white", fontSize: 13, textAlign: "left" } }, children); }
function Card({ children, style = {} }) { return h("div", { style: { background: "rgba(19,28,39,.96)", border: "1px solid rgba(255,255,255,.07)", borderRadius: 14, padding: 12, margin: "8px 0", ...style } }, children); }
function AccordionCard({ icon, title, sub, open, onToggle, children, style = {}, tone = "blue", meta = null, badge = null, primary = false }) {
    const [focused, setFocused] = useState(false);
    const base = primary && !open ? { border: "2px solid #1a9fff", background: "rgba(18,39,61,.96)", ...style } : style;
    // Collapsed: the whole card lights up. Open: only the outline and the header row,
    // so the content below stays readable.
    const focusLook = open ? { border: CARD_FOCUS_STYLE.border, boxShadow: CARD_FOCUS_STYLE.boxShadow } : { ...CARD_FOCUS_STYLE, border: primary ? "2px solid #8fd0ff" : CARD_FOCUS_STYLE.border };
    const cardStyle = { ...base, ...(focused ? focusLook : {}), transition: "background .12s ease,box-shadow .12s ease" };
    return h(Card, { style: cardStyle }, h(DialogButton, { plainFocus: true, onClick: onToggle, onFocus: () => setFocused(true), onBlur: () => setFocused(false), "aria-expanded": !!open, style: { width: "100%", minHeight: 0, padding: "1px", margin: 0, border: 0, borderRadius: 10, background: focused && open ? "linear-gradient(135deg,rgba(56,104,150,.75),rgba(30,58,90,.6))" : "transparent", boxShadow: focused && open ? "0 0 0 6px rgba(56,104,150,.45)" : "none", color: "white", textAlign: "left" } }, h("div", { style: { display: "grid", gridTemplateColumns: "30px minmax(0,1fr) auto 18px", gap: 9, alignItems: "center" } }, typeof icon === "string" ? h(IconTile, { name: icon, tone }) : icon, h("div", { style: { minWidth: 0 } }, h("div", { style: { fontWeight: 760, fontSize: 14 } }, title), sub && h("div", { style: { fontSize: 10, opacity: focused ? .85 : .58, marginTop: 1, lineHeight: 1.25, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } }, sub)), badge != null ? h("span", { style: { fontSize: 10, fontWeight: 800, color: "#06121f", background: "#c9d6e3", borderRadius: 999, padding: "1px 7px" } }, badge) : (meta ? h("span", { style: { fontSize: 10, fontWeight: 700, color: typeof meta === "object" && meta.tone === "muted" ? "#8ea2b8" : "#9fe0b8", whiteSpace: "nowrap" } }, typeof meta === "object" ? meta.text : meta) : h("span", null)), h("div", { style: { color: focused ? "#d9f0ff" : "#8ea2b8", display: "flex", justifyContent: "center" } }, h(Icon, { name: open ? "chevronDown" : "chevronRight", size: 16 })))), open && h("div", { style: { paddingTop: 9 } }, children));
}
function wifiRows(w) {
    if (!w)
        return [];
    if (w.connected === false)
        return [["Status", "Not connected"]];
    const r = [];
    if (w.ssid)
        r.push(["Network", w.ssid]);
    if (w.band)
        r.push(["Band", w.band + (w.channel ? ` · ch ${w.channel}` : "")]);
    if (w.tx_mbps != null || w.rx_mbps != null)
        r.push(["Link send / receive", `${w.tx_mbps != null ? Math.round(w.tx_mbps) : "?"} / ${w.rx_mbps != null ? Math.round(w.rx_mbps) : "?"} Mbit/s`]);
    if (w.width_mhz)
        r.push(["Channel width", `${w.width_mhz} MHz`]);
    if (w.standard)
        r.push(["Standard", w.standard]);
    if (w.signal_dbm != null)
        r.push(["Signal", `${w.signal_dbm} dBm`]);
    else if (w.signal_pct != null)
        r.push(["Signal", `${w.signal_pct}%`]);
    if (w.power_save != null)
        r.push(["Power saving", w.power_save ? "ON" : "Off"]);
    return r;
}
function timeAgo(ts) {
    const s = Math.max(0, Date.now() / 1000 - Number(ts || 0));
    if (s < 90)
        return "just now";
    if (s < 3600)
        return `${Math.round(s / 60)} min ago`;
    if (s < 86400)
        return `${Math.round(s / 3600)} h ago`;
    if (s < 172800)
        return "yesterday";
    return `${Math.round(s / 86400)} days ago`;
}
function clipGameName(appid) {
    try {
        const store = window.appStore;
        const o = store && typeof store.GetAppOverviewByAppID === "function" ? store.GetAppOverviewByAppID(Number(appid)) : null;
        if (o && o.display_name)
            return String(o.display_name);
    }
    catch (e) { }
    return `Game ${appid}`;
}
function clipMeta(c) {
    const parts = [];
    if (c.seconds != null)
        parts.push(duration(c.seconds));
    if (c.size_human)
        parts.push(c.size_human);
    parts.push(timeAgo(c.created));
    return parts.join(" · ");
}
function RecentList({ items }) {
    if (!items || !items.length)
        return null;
    return h("div", null, h("div", { style: { fontSize: 10, fontWeight: 800, letterSpacing: .9, textTransform: "uppercase", opacity: .45, margin: "14px 4px 4px" } }, "Recent"), h(Card, { style: { padding: 0 } }, items.slice(0, 3).map((f, i) => h("div", { key: f.path, style: { display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", borderTop: i ? "1px solid rgba(255,255,255,.06)" : "none" } }, h("div", { style: { minWidth: 0, flex: 1 } }, h("div", { style: { fontSize: 12, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } }, f.name), h("div", { style: { fontSize: 10, opacity: .6, marginTop: 1 } }, `${f.from ? `From ${f.from}` : "Received"} · ${f.size_human} · ${timeAgo(f.received_at)}`)), h("div", { style: { color: "#3ddc84" } }, h(Icon, { name: "check", size: 15, strokeWidth: 2.4 }))))));
}
function SubSection({ title, children, first = false }) {
    return h("div", { style: { paddingTop: first ? 0 : 10, marginTop: first ? 0 : 10, borderTop: first ? "none" : "1px solid rgba(255,255,255,.06)" } }, h("div", { style: { fontSize: 10, fontWeight: 800, letterSpacing: .8, textTransform: "uppercase", opacity: .55, marginBottom: 7 } }, title), children);
}
function updateMeta(u) {
    if (!u || !u.ok)
        return null;
    if (u.available)
        return { text: "Update available" };
    return { text: "Up to date", tone: "muted" };
}
function wifiSummary(w) {
    if (!w || w.error || w.connected !== true)
        return null;
    const q = w.signal_dbm != null ? (w.signal_dbm >= -60 ? "Strong" : (w.signal_dbm >= -70 ? "Good" : "Weak")) : null;
    return [w.band, q].filter(Boolean).join(" · ") || null;
}
function pcAddress(displayUrl) { return String(displayUrl || "").replace(/^https?:\/\//, "").replace(/[\/?#].*$/, "") || "…"; }
function pcCode(status) { const raw = status && status.pc_code && status.pc_code.code ? String(status.pc_code.code) : ""; return raw.length === 6 ? raw.slice(0, 3) + " " + raw.slice(3) : "··· ···"; }
function MiniButton({ children, onClick, tone = "normal", compact = false, block = false }) {
    const danger = tone === "danger";
    // Steam's DialogButton is full width by default; size small buttons to their text
    // (or to their grid cell with block) so they sit side by side.
    return h(DialogButton, { onClick, className: compact ? "deckyshare-compact-action" : "", style: { width: block ? "100%" : "auto", minWidth: 0, flex: block ? "1 1 0" : "0 0 auto", boxSizing: "border-box", minHeight: compact ? 26 : undefined, height: compact ? 26 : undefined, padding: compact ? "2px 6px" : "7px 9px", borderRadius: compact ? 7 : 9, border: danger ? "1px solid rgba(255,110,110,.34)" : "1px solid rgba(120,180,255,.24)", background: danger ? "rgba(255,70,70,.10)" : "rgba(68,122,184,.13)", color: danger ? "#ffd0d0" : "#d9edff", fontSize: compact ? 9 : 11, lineHeight: 1, fontWeight: 700 } }, children);
}
function DeckyShareBrandIcon({ size = 24 }) {
    return h("svg", { viewBox: "0 0 24 24", width: size, height: size, fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", style: { display: "block", color: "currentColor", flexShrink: 0 } }, h("rect", { x: "2.5", y: "2.5", width: "19", height: "19", rx: "5.5" }), h("path", { d: "M7.5 9.5h9l-2.6-2.6" }), h("path", { d: "M16.5 14.5h-9l2.6 2.6" }));
}
function BrandTile({ size = 34 }) {
    return h("div", { style: { width: size, height: size, borderRadius: Math.round(size * .3), background: "#1a9fff", color: "#06121f", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 } }, h("svg", { viewBox: "0 0 24 24", width: Math.round(size * .62), height: Math.round(size * .62), fill: "none", stroke: "currentColor", strokeWidth: 2.6, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true" }, h("path", { d: "M5 8.5h12.5l-3.2-3.2" }), h("path", { d: "M19 15.5H6.5l3.2 3.2" })));
}
function connectDeckyBackend() {
    const init = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
    if (!init || typeof init.connect !== "function")
        throw new Error("Decky loader API is not initialized");
    try {
        return init.connect(2, "DeckyShare");
    }
    catch (e) {
        return init.connect(1, "DeckyShare");
    }
}
function deckyLoaderBackend() {
    const loader = window.DeckyBackend;
    if (!loader || typeof loader.call !== "function")
        throw new Error("Decky Loader install API is unavailable");
    return loader;
}
function makePanel() {
    let backendAPI = null;
    try {
        backendAPI = connectDeckyBackend();
    }
    catch (e) {
        console.error("[DeckyShare] API connect failed", e);
    }
    return function Panel() {
        const [status, setStatus] = useState(null), [roots, setRoots] = useState([]), [path, setPath] = useState(null), [parent, setParent] = useState(null), [items, setItems] = useState([]), [err, setErr] = useState(""), [connIndex, setConnIndex] = useState(0), [deleteArmed, setDeleteArmed] = useState(null), [notifyOn, setNotifyOn] = useState(notificationsEnabled()), [copied, setCopied] = useState(false), [copiedPath, setCopiedPath] = useState(null), [updateInfo, setUpdateInfo] = useState(null), [updateBusy, setUpdateBusy] = useState(false), [updateArmed, setUpdateArmed] = useState(false), [rollbackArmed, setRollbackArmed] = useState(false), [browseQuery, setBrowseQuery] = useState(""), [browseSort, setBrowseSort] = useState("name"), [fmStorage, setFmStorage] = useState(null), [fmSelect, setFmSelect] = useState(false), [fmPicked, setFmPicked] = useState([]), [fmClip, setFmClip] = useState(null), [fmBusy, setFmBusy] = useState(false), [fmNew, setFmNew] = useState(""), [fmRename, setFmRename] = useState(null), [fmRenameValue, setFmRenameValue] = useState(""), [fmInfo, setFmInfo] = useState(null), [fmTrashArmed, setFmTrashArmed] = useState(false), [browseLimit, setBrowseLimit] = useState(50), [fmMenu, setFmMenu] = useState(false);
        const [openSections, setOpenSections] = useState({ browse: false, shots: false, clips: false, texts: false, received: false, updates: false, support: false, wifi: false });
        const [showQr, setShowQr] = useState(false), [cancelArmed, setCancelArmed] = useState(null);
        const [clips, setClips] = useState(null), [clipThumbs, setClipThumbs] = useState({}), [clipLimit, setClipLimit] = useState(8), [clipBusy, setClipBusy] = useState(false);
        const clipJobRef = useRef(null);
        const [pasteHint, setPasteHint] = useState(null);
        const composeRef = useRef(null);
        const [pasteBusy, setPasteBusy] = useState(false);
        const [typingLocal, setTypingLocal] = useState(false), [inputLog, setInputLog] = useState([]);
        const logInput = line => setInputLog(v => [...v.slice(-7), line]);
        const [shots, setShots] = useState(null), [shotThumbs, setShotThumbs] = useState({}), [shotPicked, setShotPicked] = useState([]), [shotLimit, setShotLimit] = useState(12), [shotBusy, setShotBusy] = useState(false);
        const [textDraft, setTextDraft] = useState(""), [textBusy, setTextBusy] = useState(false), [textLimit, setTextLimit] = useState(4), [clearArmed, setClearArmed] = useState(false);
        const lastReceivedRef = useRef(null);
        const transferStatesRef = useRef(new Map());
        const firstBrowseItemRef = useRef(null);
        const toggleSection = id => setOpenSections(previous => ({ ...previous, [id]: !previous[id] }));
        const [wifi, setWifi] = useState(null), [wifiBusy, setWifiBusy] = useState(false);
        async function loadWifi() {
            if (wifiBusy)
                return;
            setWifiBusy(true);
            try {
                const r = await call("wifi_info");
                setWifi(r && r.ok ? r.wifi : { error: (r && r.error) || "Wi-Fi details unavailable" });
            }
            catch (e) {
                setWifi({ error: String(e && e.message || e) });
            }
            finally {
                setWifiBusy(false);
            }
        }
        async function call(method, args = {}) {
            if (!backendAPI)
                backendAPI = connectDeckyBackend();
            if (!backendAPI || typeof backendAPI.call !== "function")
                throw new Error("Decky backend call API unavailable");
            const r = Object.keys(args).length ? await backendAPI.call(method, args) : await backendAPI.call(method);
            return r && Object.prototype.hasOwnProperty.call(r, "result") ? r.result : r;
        }
        function observeTransfers(transfers) {
            const next = new Map();
            for (const t of transfers || []) {
                const prev = transferStatesRef.current.get(t.id);
                if (prev !== t.status && (t.status === "failed" || (t.status === "complete" && t.direction === "download")))
                    showTransferResult(backendAPI, t);
                next.set(t.id, t.status);
            }
            transferStatesRef.current = next;
        }
        async function bootstrap() {
            try {
                setErr("");
                // Right after an install or update Decky can take a while to start the
                // Python backend, so retry a few times before showing an error.
                let b = null, last = null;
                for (let attempt = 0; attempt < 4 && !b; attempt++) {
                    try {
                        b = await withTimeout(call("bootstrap"), 6500 + attempt * 3500, "Backend startup");
                        if (!b || !b.ok) {
                            b = null;
                            throw new Error("Backend returned invalid startup data");
                        }
                    }
                    catch (e) {
                        last = e;
                        if (attempt < 3)
                            await new Promise(r => setTimeout(r, 1500));
                    }
                }
                if (!b)
                    throw last || new Error("Backend did not start");
                setStatus(b);
                setRoots(b.roots || []);
                setConnIndex(0);
                if (b.received && b.received.length)
                    lastReceivedRef.current = b.received[0].path;
                transferStatesRef.current = new Map((b.transfers || []).map(t => [t.id, t.status]));
            }
            catch (e) {
                setErr("Backend error: " + String(e && e.message || e));
            }
        }
        async function refreshStatus() {
            try {
                const s = await call("status");
                if (s && s.ok) {
                    const newest = s.received && s.received.length ? s.received[0] : null;
                    if (newest && lastReceivedRef.current && newest.path !== lastReceivedRef.current)
                        queueReceivedToast(backendAPI, newest);
                    if (newest)
                        lastReceivedRef.current = newest.path;
                    observeTransfers(s.transfers || []);
                    setStatus(x => ({ ...x, ...s }));
                }
            }
            catch (e) {
                setErr("Status: " + String(e && e.message || e));
            }
        }
        async function browse(p) { try {
            const j = await call("browse", { path: p });
            setPath(j.path);
            setParent(j.parent);
            setItems(j.items || []);
            setFmStorage(j.storage || null);
            setBrowseQuery("");
            setBrowseLimit(50);
            setFmPicked([]);
            setFmSelect(false);
            setFmInfo(null);
            setFmRename(null);
            setFmMenu(false);
            setErr("");
        }
        catch (e) {
            setErr("Browse: " + String(e && e.message || e));
        } }
        function leaveBrowser() {
            setPath(null);
            setParent(null);
            setItems([]);
            setBrowseQuery("");
            setBrowseLimit(50);
            setFmPicked([]);
            setFmSelect(false);
            setFmInfo(null);
            setFmRename(null);
            setFmMenu(false);
        }
        function navigateBack() {
            if (!path)
                return false;
            const atLocationRoot = (roots || []).some(r => r.path === path);
            if (atLocationRoot || !parent)
                leaveBrowser();
            else
                browse(parent);
            return true;
        }
        function consumeCancel(e) {
            try {
                if (e && typeof e.preventDefault === "function")
                    e.preventDefault();
            }
            catch (_e) { }
            try {
                if (e && typeof e.stopPropagation === "function")
                    e.stopPropagation();
            }
            catch (_e) { }
        }
        function handleControllerBack(e) {
            if (fmMenu) {
                consumeCancel(e);
                setFmMenu(false);
                return;
            }
            if (fmNew) {
                consumeCancel(e);
                setFmNew("");
                return;
            }
            if (fmRename) {
                consumeCancel(e);
                setFmRename(null);
                setFmRenameValue("");
                return;
            }
            if (fmInfo) {
                consumeCancel(e);
                setFmInfo(null);
                return;
            }
            if (fmSelect) {
                consumeCancel(e);
                setFmSelect(false);
                setFmPicked([]);
                return;
            }
            if (status && status.selected) {
                consumeCancel(e);
                clearSelection();
                return;
            }
            if (path) {
                consumeCancel(e);
                navigateBack();
            }
        }
        async function selectFile(p) { try {
            await call("select_file", { path: p });
            await refreshStatus();
        }
        catch (e) {
            setErr("Selection: " + String(e && e.message || e));
        } }
        async function clearSelection() { try {
            await call("clear_selection");
            await refreshStatus();
        }
        catch (e) {
            setErr("Clear selection: " + String(e && e.message || e));
        } }
        async function showReceivedFolder(p) {
            try {
                await call("clear_selection");
                setStatus(s => ({ ...s, selected: null }));
                await browse(dirname(p));
            }
            catch (e) {
                setErr("Show folder: " + String(e && e.message || e));
            }
        }
        async function copyText(text, label = "Path") {
            if (!text)
                return false;
            const ok = await copyToClipboard(text);
            if (ok) {
                setCopiedPath(text);
                setErr("");
                setTimeout(() => setCopiedPath(p => p === text ? null : p), 1600);
                return true;
            }
            setCopiedPath(null);
            setErr(`Copy ${label.toLowerCase()} failed — clipboard is blocked in this Decky view`);
            return false;
        }
        async function deleteReceived(p) {
            if (deleteArmed !== p) {
                setDeleteArmed(p);
                return;
            }
            try {
                setDeleteArmed(null);
                const r = await call("delete_received", { path: p });
                setStatus(s => ({ ...s, received: r && r.received ? r.received : (s.received || []).filter(x => x.path !== p) }));
            }
            catch (e) {
                setDeleteArmed(null);
                setErr("Delete: " + String(e && e.message || e));
            }
        }
        function fmToggle(it) { setFmSelect(true); setFmInfo(null); setFmPicked(v => v.includes(it.path) ? v.filter(x => x !== it.path) : [...v, it.path]); }
        async function fmMkdir() { if (!path || !fmNew.trim() || fmBusy)
            return; setFmBusy(true); try {
            await call("file_mkdir", { parent: path, name: fmNew.trim() });
            setFmNew("");
            await browse(path);
        }
        catch (e) {
            setErr("New folder: " + String(e && e.message || e));
        }
        finally {
            setFmBusy(false);
        } }
        function fmStage(mode) { if (fmPicked.length) {
            setFmClip({ mode, paths: fmPicked.slice() });
            setFmPicked([]);
            setFmSelect(false);
        } }
        async function fmPaste() { if (!fmClip || !path || fmBusy)
            return; const c = fmClip; setFmBusy(true); try {
            await call(c.mode === "move" ? "file_move" : "file_copy", { paths: c.paths, destination: path });
            setFmClip(null);
            await browse(path);
        }
        catch (e) {
            setErr("Paste: " + String(e && e.message || e));
        }
        finally {
            setFmBusy(false);
        } }
        async function fmDoRename() { if (!fmRename || !fmRenameValue.trim() || fmBusy)
            return; setFmBusy(true); try {
            await call("file_rename", { path: fmRename.path, name: fmRenameValue.trim() });
            setFmRename(null);
            setFmRenameValue("");
            await browse(path);
        }
        catch (e) {
            setErr("Rename: " + String(e && e.message || e));
        }
        finally {
            setFmBusy(false);
        } }
        async function fmDetails(it) { try {
            const r = await call("file_details", { path: it.path });
            setFmInfo(r.item || null);
        }
        catch (e) {
            setErr("Details: " + String(e && e.message || e));
        } }
        async function fmTrash() { if (!fmPicked.length || fmBusy)
            return; if (!fmTrashArmed) {
            setFmTrashArmed(true);
            setTimeout(() => setFmTrashArmed(false), 7000);
            return;
        } setFmBusy(true); try {
            await call("file_trash", { paths: fmPicked });
            setFmPicked([]);
            setFmSelect(false);
            setFmTrashArmed(false);
            await browse(path);
            await refreshStatus();
        }
        catch (e) {
            setErr("Trash: " + String(e && e.message || e));
        }
        finally {
            setFmBusy(false);
        } }
        async function copyToClipboard(text) {
            if (!text)
                return false;
            let ok = false;
            try {
                if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
                    try {
                        await navigator.clipboard.writeText(text);
                        ok = true;
                    }
                    catch (e) { }
                }
                if (!ok && typeof document !== "undefined") {
                    const ta = document.createElement("textarea");
                    ta.value = text;
                    ta.setAttribute("readonly", "");
                    ta.style.position = "fixed";
                    ta.style.left = "-9999px";
                    ta.style.top = "0";
                    ta.style.opacity = "0";
                    document.body.appendChild(ta);
                    ta.focus();
                    ta.select();
                    if (typeof ta.setSelectionRange === "function")
                        ta.setSelectionRange(0, text.length);
                    try {
                        ok = !!document.execCommand("copy");
                    }
                    catch (e) {
                        ok = false;
                    }
                    document.body.removeChild(ta);
                }
            }
            catch (e) {
                ok = false;
            }
            return ok;
        }
        function toggleNotifications() { const next = !notifyOn; setNotifyOn(next); saveNotificationsEnabled(next); if (next)
            notifySeen.clear();
        else {
            receivedBatch = [];
            if (receivedBatchTimer) {
                clearTimeout(receivedBatchTimer);
                receivedBatchTimer = null;
            }
        } }
        async function checkUpdate(force = false) {
            if (updateBusy)
                return;
            setUpdateBusy(true);
            setUpdateArmed(false);
            setRollbackArmed(false);
            try {
                const r = await call("check_update", { force: !!force });
                setUpdateInfo(r || { ok: false, error: "No update response" });
                if (r && !r.ok)
                    setErr("Update: " + String(r.error || "check failed"));
                else if (err.startsWith("Update:"))
                    setErr("");
            }
            catch (e) {
                const msg = String(e && e.message || e);
                setUpdateInfo({ ok: false, error: msg });
                setErr("Update: " + msg);
            }
            finally {
                setUpdateBusy(false);
            }
        }
        async function installUpdate() {
            if (updateBusy || !updateInfo || !updateInfo.available)
                return;
            if (!updateArmed) {
                setUpdateArmed(true);
                setTimeout(() => setUpdateArmed(false), 7000);
                return;
            }
            setUpdateBusy(true);
            setUpdateArmed(false);
            try {
                const r = await call("install_update", { tag: updateInfo.latest_tag });
                if (!r || !r.ok || !r.request_install)
                    throw new Error(r && r.error || "Update preparation failed");
                const loader = deckyLoaderBackend();
                await loader.call("utilities/install_plugin", r.artifact, r.name || "DeckyShare", r.version, r.sha256, Number(r.install_type || 2));
                setUpdateInfo(x => ({ ...x, installer_prompted: true, prepared_version: r.version }));
                setErr("");
                toast(backendAPI, `Decky confirmation opened for v${r.version}`);
            }
            catch (e) {
                const msg = String(e && e.message || e);
                setErr("Update: " + msg);
                setUpdateInfo(x => ({ ...x, install_error: msg }));
            }
            finally {
                setUpdateBusy(false);
            }
        }
        async function rollbackUpdate() {
            if (updateBusy || !updateInfo || !updateInfo.rollback_available)
                return;
            if (!rollbackArmed) {
                setRollbackArmed(true);
                setTimeout(() => setRollbackArmed(false), 7000);
                return;
            }
            setUpdateBusy(true);
            setRollbackArmed(false);
            try {
                const r = await call("rollback_update");
                if (!r || !r.ok)
                    throw new Error(r && r.error || "Rollback failed");
                setUpdateInfo(x => ({ ...x, ...r, installed_now: true, current: r.installed, rollback_available: false }));
                setErr("");
                toast(backendAPI, `Restored DeckyShare ${r.installed} • reload required`);
            }
            catch (e) {
                const msg = String(e && e.message || e);
                setErr("Rollback: " + msg);
            }
            finally {
                setUpdateBusy(false);
            }
        }
        async function loadClips() {
            if (clipBusy)
                return;
            setClipBusy(true);
            try {
                const r = await call("list_clips");
                if (!r || !r.ok)
                    throw new Error(r && r.error || "Could not read game recordings");
                setClips(r.clips || []);
                if (r.export)
                    setStatus(x => ({ ...x, clip_export: r.export }));
            }
            catch (e) {
                setClips([]);
                setErr("Clips: " + String(e && e.message || e));
            }
            finally {
                setClipBusy(false);
            }
        }
        async function loadClipThumbs(list) {
            for (const c of list) {
                if (!c.has_thumbnail || clipThumbs[c.id])
                    continue;
                try {
                    const r = await call("clip_thumbnail", { id: c.id });
                    if (r && r.ok && r.src)
                        setClipThumbs(t => ({ ...t, [c.id]: r.src }));
                }
                catch (e) { }
            }
        }
        async function exportClip(c) {
            const job = status && status.clip_export;
            if (job && job.state === "working")
                return;
            try {
                const r = await call("export_clip", { id: c.id, game: clipGameName(c.appid) });
                if (!r || !r.ok)
                    throw new Error(r && r.error || "Could not prepare the clip");
                setStatus(x => ({ ...x, clip_export: r.export }));
                await refreshStatus();
            }
            catch (e) {
                setErr("Clip: " + String(e && e.message || e));
            }
        }
        async function loadShots() {
            if (shotBusy)
                return;
            setShotBusy(true);
            try {
                const r = await call("list_screenshots");
                if (!r || !r.ok)
                    throw new Error(r && r.error || "Could not read screenshots");
                setShots(r.items || []);
            }
            catch (e) {
                setShots([]);
                setErr("Screenshots: " + String(e && e.message || e));
            }
            finally {
                setShotBusy(false);
            }
        }
        async function loadShotThumbs(list) {
            const need = list.filter(x => x && !shotThumbs[x.id]).map(x => x.id);
            for (let i = 0; i < need.length; i += 12) {
                try {
                    const r = await call("screenshot_thumbnails", { ids: need.slice(i, i + 12) });
                    if (r && r.thumbs)
                        setShotThumbs(t => ({ ...t, ...r.thumbs }));
                }
                catch (e) { }
            }
        }
        function toggleShot(id) { setShotPicked(v => v.includes(id) ? v.filter(x => x !== id) : [...v, id]); }
        async function sendShots() {
            if (!shotPicked.length)
                return;
            try {
                const r = await call("share_files", { paths: shotPicked });
                if (!r || !r.ok)
                    throw new Error(r && r.error || "Could not share");
                toast(backendAPI, `${shotPicked.length} picture${shotPicked.length === 1 ? "" : "s"} ready • open Get from Deck on your phone`);
                setShotPicked([]);
                await refreshStatus();
            }
            catch (e) {
                setErr("Screenshots: " + String(e && e.message || e));
            }
        }
        async function clearShared() { try {
            await call("clear_shared");
            await refreshStatus();
        }
        catch (e) {
            setErr("Screenshots: " + String(e && e.message || e));
        } }
        useEffect(() => { if (openSections.shots && status)
            loadShots(); }, [openSections.shots, !!status]);
        useEffect(() => { if (shots && openSections.shots)
            loadShotThumbs(shots.slice(0, shotLimit)); }, [shots, shotLimit, openSections.shots]);
        async function pasteFromDeck() {
            if (pasteBusy)
                return;
            setPasteBusy(true);
            const isRc = String(status && status.version || "").includes("-rc");
            try {
                let text = null, how = "";
                try {
                    if (navigator.clipboard && typeof navigator.clipboard.readText === "function") {
                        text = await Promise.race([navigator.clipboard.readText(), new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), 1200))]);
                        how = "browser";
                    }
                }
                catch (e) {
                    if (isRc)
                        logInput("browser clipboard: " + String(e && e.message || e).slice(0, 60));
                }
                if (!text) {
                    const r = await call("read_clipboard");
                    if (!r || !r.ok)
                        throw new Error(r && r.error || "Clipboard is empty");
                    text = r.text;
                    how = r.how;
                }
                const el = composeRef.current;
                if (el) {
                    el.value = text;
                    try {
                        el.focus();
                    }
                    catch (e) { }
                }
                setTextDraft(text);
                if (isRc)
                    logInput(`Paste button: ${String(text).length} chars via ${how}`);
            }
            catch (e) {
                setErr("Paste: " + String(e && e.message || e));
            }
            finally {
                setPasteBusy(false);
            }
        }
        async function sendText() {
            const el = composeRef.current;
            const text = String(el && typeof el.value === "string" ? el.value : textDraft).trim();
            if (!text || textBusy)
                return;
            setTextBusy(true);
            try {
                const r = await call("send_text", { text });
                if (!r || !r.ok)
                    throw new Error(r && r.error || "Could not send");
                if (composeRef.current)
                    composeRef.current.value = "";
                setTextDraft("");
                setStatus(x => ({ ...x, texts: r.texts || x.texts }));
                toast(backendAPI, "Text sent • open the Text tab on your phone");
            }
            catch (e) {
                setErr("Text: " + String(e && e.message || e));
            }
            finally {
                setTextBusy(false);
            }
        }
        async function deleteText(id) { try {
            const r = await call("delete_text", { id });
            setStatus(x => ({ ...x, texts: r && r.texts || [] }));
        }
        catch (e) {
            setErr("Text: " + String(e && e.message || e));
        } }
        async function clearTexts() {
            if (!clearArmed) {
                setClearArmed(true);
                setTimeout(() => setClearArmed(false), 5000);
                return;
            }
            setClearArmed(false);
            try {
                await call("clear_texts");
                setStatus(x => ({ ...x, texts: [] }));
            }
            catch (e) {
                setErr("Text: " + String(e && e.message || e));
            }
        }
        async function typeOnDeck(t) {
            if (typingLocal)
                return;
            const steamSend = (() => { try {
                const sc = window.SteamClient;
                return sc && sc.Input && typeof sc.Input.ControllerKeyboardSendText === "function" ? sc.Input.ControllerKeyboardSendText.bind(sc.Input) : null;
            }
            catch (e) {
                return null;
            } })();
            const closeMenu = () => { try {
                const nav = DeckyUI.Router || DeckyUI.Navigation;
                if (nav && typeof nav.CloseSideMenus === "function")
                    nav.CloseSideMenus();
            }
            catch (e) { } };
            if (steamSend) {
                // Steam's own keyboard input: types into whatever has focus, games included.
                setTypingLocal(true);
                try {
                    closeMenu();
                    await new Promise(r => setTimeout(r, 600));
                    for (const ch of Array.from(String(t.text))) {
                        steamSend(ch);
                        await new Promise(r => setTimeout(r, 6));
                    }
                }
                catch (e) {
                    setErr("Type: " + String(e && e.message || e));
                }
                finally {
                    setTypingLocal(false);
                }
                return;
            }
            // Older Steam: fall back to a temporary virtual keyboard on the Deck.
            const job = status && status.typing;
            if (job && (job.state === "waiting" || job.state === "typing"))
                return;
            try {
                const r = await call("type_text", { id: t.id, delay: 1.5 });
                if (!r || !r.ok)
                    throw new Error(r && r.error || "Could not type");
                setStatus(x => ({ ...x, typing: r.typing }));
                if (r.typing && r.typing.skipped)
                    toast(backendAPI, `${r.typing.skipped} special character(s) can't be typed and will be skipped`);
                closeMenu();
            }
            catch (e) {
                setErr("Type: " + String(e && e.message || e));
            }
        }
        async function copyClipboardItem(t) {
            const ok = await copyText(t.text, "Text");
            if (!ok)
                return;
            setPasteHint(t.id);
            setTimeout(() => setPasteHint(x => x === t.id ? null : x), 8000);
            toast(backendAPI, "Copied • tap Paste on the Steam keyboard");
        }
        function openLink(url) {
            try {
                if (DeckyUI.Navigation && typeof DeckyUI.Navigation.NavigateToExternalWeb === "function") {
                    DeckyUI.Navigation.NavigateToExternalWeb(url);
                    return;
                }
            }
            catch (e) { }
            try {
                window.open(url, "_blank");
            }
            catch (e) {
                setErr("Open link failed");
            }
        }
        async function cancelClipExport() { try {
            await call("cancel_clip_export");
            await refreshStatus();
        }
        catch (e) {
            setErr("Clip: " + String(e && e.message || e));
        } }
        useEffect(() => { if (openSections.clips && status)
            loadClips(); }, [openSections.clips, !!status]);
        useEffect(() => { if (clips && openSections.clips)
            loadClipThumbs(clips.slice(0, clipLimit)); }, [clips, clipLimit, openSections.clips]);
        useEffect(() => {
            const job = status && status.clip_export;
            const prev = clipJobRef.current;
            if (job && job.state === "done" && prev && prev.id === job.id && prev.state === "working")
                toast(backendAPI, "Clip ready • on your phone tap Get from Deck");
            if (job && job.state === "error" && prev && prev.state === "working")
                setErr("Clip: " + String(job.error || "failed"));
            clipJobRef.current = job ? { id: job.id, state: job.state } : null;
        }, [status && status.clip_export && status.clip_export.state, status && status.clip_export && status.clip_export.id]);
        const typingState = status && status.typing && status.typing.state;
        useEffect(() => { const j = status && status.typing; if (typingState === "error" && j && j.error && j.error !== "Cancelled")
            setErr("Type: " + j.error); }, [typingState]);
        useEffect(() => { bootstrap(); }, []);
        useEffect(() => { if (!status)
            return; loadWifi(); checkUpdate(false); }, [!!status]);
        async function cancelTransfer(t) {
            if (cancelArmed !== t.id) {
                setCancelArmed(t.id);
                setTimeout(() => setCancelArmed(x => x === t.id ? null : x), 4000);
                return;
            }
            setCancelArmed(null);
            try {
                const r = await call("cancel_transfer", { id: t.id });
                if (r && r.ok === false && r.error)
                    setErr("Cancel: " + r.error);
                await refreshStatus();
            }
            catch (e) {
                setErr("Cancel: " + String(e && e.message || e));
            }
        }
        useEffect(() => { if (!status)
            return; const t = setInterval(refreshStatus, path ? 4000 : 1500); return () => clearInterval(t); }, [!!status, !!path]);
        useEffect(() => { if (!path || status && status.selected)
            return; const t = setTimeout(() => { try {
            if (firstBrowseItemRef.current && typeof firstBrowseItemRef.current.focus === "function")
                firstBrowseItemRef.current.focus();
        }
        catch (e) { } }, 80); return () => clearTimeout(t); }, [path, items, status && status.selected]);
        const busy = !!(status && status.transfers && status.transfers.some(t => t.status === "active"));
        const conns = status && status.addresses || [];
        const activeConn = conns[Math.min(connIndex, Math.max(0, conns.length - 1))] || null;
        const displayUrl = activeConn ? activeConn.url : status && status.address || "";
        const displayQr = activeConn ? activeConn.qr_data : status && status.qr_data || null;
        const browseCrumbs = path ? browseCrumbsFor(path, roots) : [];
        const visibleBrowseItems = useMemo(() => path ? browseVisibleItems(items, browseQuery, browseSort) : [], [path, items, browseQuery, browseSort]);
        const fmChosen = useMemo(() => items.filter(x => fmPicked.includes(x.path)), [items, fmPicked]);
        if (err && !status)
            return h("div", { style: { padding: 12 } }, err, h(Btn, { onClick: bootstrap }, "Retry backend"));
        if (!status)
            return h("div", { style: { padding: 12 } }, "Starting DeckyShare backend…");
        return h(Focusable, { onCancel: handleControllerBack, className: "deckyshare-root", style: { padding: "4px 8px 18px", fontSize: 14, color: "white" } }, h("style", null, ".deckyshare-root .deckyshare-compact-action{min-width:0!important;min-height:26px!important;height:26px!important;padding:2px 5px!important;display:flex!important;align-items:center!important;justify-content:center!important;white-space:nowrap!important;overflow:hidden!important}.deckyshare-root .deckyshare-compact-action>div{min-width:0!important;min-height:0!important;height:100%!important;width:100%!important;display:flex!important;align-items:center!important;justify-content:center!important;overflow:hidden!important;text-overflow:ellipsis!important}.deckyshare-root .deckyshare-action:focus{animation:none!important}"), h("div", { style: { display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 650, color: status.server_self_test ? "#9fe0b8" : "#ffb3b3", padding: "2px 4px 4px" } }, h("span", { style: { width: 7, height: 7, borderRadius: "50%", background: status.server_self_test ? "#3ddc84" : "#ff7070", flexShrink: 0 } }), h("span", { style: { flex: 1 } }, status.server_self_test ? "Ready · same Wi-Fi as your phone" : "Server unavailable"), h("span", { style: { fontSize: 10, fontWeight: 700, color: "#8ea2b8" } }, status.version ? `v${status.version}` : "")), h(TransferHero, { transfers: status.transfers, onCancel: cancelTransfer, armed: cancelArmed }), busy && wifi && wifiSummary(wifi) && h("div", { style: { display: "flex", alignItems: "center", gap: 7, fontSize: 11, opacity: .7, padding: "0 6px 2px" } }, h(Icon, { name: "wifi", size: 13 }), `Wi-Fi ${wifiSummary(wifi)}`), (!busy || showQr) && h(Card, { style: { border: "1px solid rgba(66,153,255,.28)" } }, h("div", { style: { display: "flex", gap: 12, alignItems: "center" } }, displayQr ? h("img", { src: displayQr, style: { width: 88, height: 88, background: "white", padding: 5, borderRadius: 10, flexShrink: 0 } }) : h("div", { style: { width: 88, height: 88, borderRadius: 10, background: "rgba(255,255,255,.06)", flexShrink: 0 } }), h("div", { style: { minWidth: 0, display: "flex", flexDirection: "column", gap: 4 } }, h("div", { style: { fontSize: 14, fontWeight: 780 } }, "Scan to connect"), h("div", { style: { fontSize: 11, opacity: .65, lineHeight: 1.35 } }, "Open the camera on your phone and point it at the code."))), h("div", { style: { marginTop: 10, paddingTop: 9, borderTop: "1px solid rgba(255,255,255,.07)" } }, h("div", { style: { fontSize: 10, opacity: .6, marginBottom: 4 } }, "On a computer, open this in a browser and enter the code"), h("div", { style: { display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 } }, h("span", { style: { fontSize: 13, fontWeight: 800, color: "#79cbff", fontFamily: "monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", minWidth: 0 } }, pcAddress(displayUrl)), h("span", { style: { fontSize: 16, fontWeight: 850, letterSpacing: 1.2, fontFamily: "monospace", whiteSpace: "nowrap" } }, pcCode(status)))), conns.length > 1 && h("div", { style: { marginTop: 9 } }, h("div", { style: { fontSize: 10, opacity: .52, marginBottom: 4 } }, "Network"), conns.map((c, i) => h(DialogButton, { key: c.ip, onClick: () => { setConnIndex(i); setCopied(false); }, style: { padding: "5px 7px", margin: "2px 3px 2px 0", borderRadius: 7, border: i === connIndex ? "1px solid #66c0f4" : "1px solid rgba(255,255,255,.10)", background: i === connIndex ? "rgba(102,192,244,.16)" : "transparent", color: "white", fontSize: 10 } }, c.interface)))), h(AccordionCard, { icon: "send", primary: true, title: "Send to phone", sub: status.selected ? `Ready: ${status.selected.name}` : (path ? (browseCrumbs.map(c => c.label).join(" › ") || "Current folder") : "Pick a file on the Deck"), open: openSections.browse, onToggle: () => toggleSection("browse"), style: { border: "1px solid rgba(120,180,255,.19)" } }, !status.selected && !path && h("div", null, roots.map(r => h(DialogButton, { key: r.path, onClick: () => browse(r.path), style: { width: "100%", padding: "9px 10px", margin: "4px 0", borderRadius: 11, border: "1px solid rgba(255,255,255,.06)", background: "rgba(255,255,255,.035)", color: "white", textAlign: "left" } }, h("div", { style: { display: "flex", alignItems: "center", gap: 9 } }, h("div", { style: { width: 32, height: 32, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(26,159,255,.12)", color: "#7cc4ff" } }, h(Icon, { name: r.name.startsWith("Drive:") ? "drive" : (/^home$/i.test(r.name) ? "home" : (/video/i.test(r.name) ? "video" : (/download/i.test(r.name) ? "inbox" : (/desktop/i.test(r.name) ? "monitor" : "folder")))), size: 17 })), h("div", { style: { minWidth: 0, flex: 1, fontWeight: 730, fontSize: 11, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } }, r.name), h("div", { style: { fontSize: 15, opacity: .34 } }, "›"))))), status.selected ? h("div", { style: { padding: 10, borderRadius: 11, background: "rgba(73,151,220,.10)", border: "1px solid rgba(100,175,240,.16)" } }, h("div", { style: { display: "flex", gap: 9, alignItems: "center" } }, h("div", { style: { width: 34, height: 34, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(102,192,244,.10)", color: "#7cc4ff" } }, browseFileIcon(status.selected, 18)), h("div", { style: { minWidth: 0, flex: 1 } }, h("div", { style: { fontWeight: 750, wordBreak: "break-word" } }, status.selected.name), h("div", { style: { fontSize: 11, opacity: .6, marginTop: 2 } }, status.selected.size_human))), h(Btn, { onClick: clearSelection }, "Choose another file")) : path && h("div", null, fmNew && h("div", { style: { display: "grid", gridTemplateColumns: "1fr auto", gap: 6, marginBottom: 7 } }, h(TextField, { value: fmNew === "New folder" ? "" : fmNew, onChange: e => setFmNew(e.target.value), placeholder: "Folder name", style: { minWidth: 0, padding: "8px", borderRadius: 8, background: "#0c1a2b", color: "white", border: "1px solid rgba(120,180,255,.18)" } }), h(MiniButton, { onClick: fmMkdir }, "Create")), fmClip && h("div", { style: { padding: 7, borderRadius: 9, marginBottom: 7, background: "rgba(255,190,75,.08)", border: "1px solid rgba(255,190,75,.20)" } }, h("div", { style: { fontSize: 10, marginBottom: 5 } }, `${fmClip.mode === "move" ? "Move" : "Copy"} ${fmClip.paths.length} item(s) here?`), h("div", { style: { display: "flex", gap: 5 } }, h(MiniButton, { onClick: fmPaste }, "Paste here"), h(MiniButton, { onClick: () => setFmClip(null) }, "Cancel"))), fmRename && h("div", { style: { display: "grid", gridTemplateColumns: "1fr auto", gap: 6, marginBottom: 7 } }, h(TextField, { value: fmRenameValue, onChange: e => setFmRenameValue(e.target.value), style: { minWidth: 0, padding: "8px", borderRadius: 8, background: "#0c1a2b", color: "white", border: "1px solid rgba(120,180,255,.18)" } }), h(MiniButton, { onClick: fmDoRename }, "Rename")), fmInfo && h("div", { style: { padding: 8, borderRadius: 9, marginBottom: 7, background: "rgba(255,255,255,.025)", border: "1px solid rgba(120,180,255,.12)", fontSize: 9 } }, h("div", { style: { fontWeight: 760, fontSize: 11 } }, fmInfo.name), h("div", { style: { opacity: .55, wordBreak: "break-all", marginTop: 3 } }, fmInfo.path), h("div", { style: { opacity: .55, marginTop: 2 } }, fmInfo.type === "dir" ? `Folder${fmInfo.item_count != null ? ` • ${fmInfo.item_count} item(s)` : ""}` : `${fmInfo.size_human}${fmInfo.mime ? ` • ${fmInfo.mime}` : ""}`)), h("div", { style: { display: "grid", gridTemplateColumns: "32px minmax(0,1fr)", gap: 6, alignItems: "center", marginBottom: 5 } }, h(DialogButton, { className: "deckyshare-compact-action", onClick: navigateBack, style: { width: 32, height: 26, minWidth: 32, minHeight: 26, padding: 0, margin: 0, borderRadius: 7, border: "1px solid rgba(120,180,255,.16)", background: "rgba(255,255,255,.025)", color: "#d9edff", fontSize: 15, fontWeight: 800 } }, "←"), h("div", { title: path, style: { minWidth: 0, height: 26, boxSizing: "border-box", padding: "6px 8px", borderRadius: 7, background: "rgba(38,68,101,.34)", border: "1px solid rgba(120,180,255,.14)", color: "#dceeff", fontSize: 9, fontWeight: 680, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, browseCrumbs.map(c => c.label).join(" › ") || path)), h("div", { style: { display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 4, marginBottom: 6 } }, h(MiniButton, { compact: true, onClick: () => { setPath(null); setParent(null); setItems([]); setBrowseQuery(""); } }, "Locations"), h(MiniButton, { compact: true, onClick: () => { setFmSelect(v => !v); setFmPicked([]); setFmInfo(null); } }, fmSelect ? "Done" : "Select"), h(MiniButton, { compact: true, onClick: () => setFmNew(fmNew ? "" : "New folder") }, fmNew ? "Cancel" : "New folder")), fmStorage && h("div", { style: { fontSize: 8, opacity: .46, margin: "0 1px 6px" } }, `${fmStorage.used_human} used • ${fmStorage.free_human} free`), h("div", { style: { display: "grid", gridTemplateColumns: "1fr auto", gap: 6, marginBottom: 6 } }, h(TextField, { value: browseQuery, onChange: e => { setBrowseQuery(e.target.value); setBrowseLimit(50); }, placeholder: "Search files", style: { minWidth: 0, width: "100%", boxSizing: "border-box", padding: "9px 10px", borderRadius: 10, border: "1px solid rgba(120,180,255,.18)", background: "rgba(7,17,29,.48)", color: "white", fontSize: 11, outline: "none" } }), h(DialogButton, { onClick: () => { const next = browseSort === "name" ? "date" : browseSort === "date" ? "size" : "name"; setBrowseSort(next); setBrowseLimit(50); }, style: { minWidth: 82, padding: "7px 8px", borderRadius: 10, border: "1px solid rgba(120,180,255,.16)", background: "rgba(255,255,255,.025)", color: "#d9edff", fontSize: 9, fontWeight: 720, whiteSpace: "nowrap" } }, `Sort: ${browseSort === "date" ? "Newest" : browseSort === "size" ? "Largest" : "Name"}`)), h("div", { style: { fontSize: 9, opacity: .42, margin: "4px 1px 7px" } }, `${visibleBrowseItems.length} item${visibleBrowseItems.length === 1 ? "" : "s"}${browseQuery ? ` matching “${browseQuery}”` : ""}`), !visibleBrowseItems.length ? h("div", { style: { padding: "15px 8px", textAlign: "center", fontSize: 11, opacity: .5, border: "1px dashed rgba(120,180,255,.14)", borderRadius: 10 } }, browseQuery ? "No matching items in this folder" : "This folder is empty") : visibleBrowseItems.slice(0, browseLimit).map((it, index) => h(DialogButton, { key: it.path, ref: index === 0 ? firstBrowseItemRef : null, onClick: () => fmSelect ? fmToggle(it) : (it.type === "dir" ? browse(it.path) : selectFile(it.path)), onFocus: e => { e.currentTarget.style.borderColor = "#66c0f4"; e.currentTarget.style.background = "rgba(35,72,108,.68)"; }, onBlur: e => { const picked = fmPicked.includes(it.path); e.currentTarget.style.borderColor = picked ? "#66c0f4" : "rgba(120,180,255,.11)"; e.currentTarget.style.background = picked ? "rgba(48,92,132,.68)" : "rgba(20,39,63,.46)"; }, style: { width: "100%", padding: "5px 7px", margin: "2px 0", borderRadius: 9, border: fmPicked.includes(it.path) ? "1px solid #66c0f4" : "1px solid rgba(120,180,255,.11)", background: fmPicked.includes(it.path) ? "rgba(48,92,132,.68)" : "rgba(20,39,63,.46)", boxShadow: fmPicked.includes(it.path) ? "inset 3px 0 0 #66c0f4" : "none", color: "white", textAlign: "left", transition: "background .12s ease,border-color .12s ease" } }, h("div", { style: { display: "grid", gridTemplateColumns: "26px minmax(0,1fr) 18px", gap: 7, alignItems: "center" } }, h("div", { style: { width: 26, height: 26, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center", background: it.type === "dir" ? "rgba(102,192,244,.09)" : "rgba(255,255,255,.04)", color: it.type === "dir" ? "#7cc4ff" : "#b8c7d6", flexShrink: 0 } }, browseFileIcon(it, 14)), h("div", { style: { minWidth: 0 } }, h("div", { style: { fontWeight: 720, fontSize: 10, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } }, it.name), h("div", { style: { fontSize: 9, opacity: .46, marginTop: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } }, browseDate(it.mtime) || (it.type === "dir" ? "Folder" : ""))), h("div", { style: { fontSize: 14, lineHeight: 1, textAlign: "center", fontWeight: 850, color: fmSelect && fmPicked.includes(it.path) ? "#9edcff" : "#70869a", opacity: fmSelect || it.type === "dir" ? 1 : .35 } }, fmSelect ? (fmPicked.includes(it.path) ? "✓" : "○") : (it.type === "dir" ? "›" : ""))))), visibleBrowseItems.length > browseLimit && h(DialogButton, { onClick: () => setBrowseLimit(x => Math.min(x + 50, visibleBrowseItems.length)), style: { width: "100%", padding: "8px", marginTop: 6, borderRadius: 9, border: "1px solid rgba(120,180,255,.16)", background: "rgba(255,255,255,.025)", color: "#bde7ff", fontSize: 10, fontWeight: 700 } }, `Show 50 more • ${browseLimit} of ${visibleBrowseItems.length}`), fmSelect && fmChosen.length > 0 && h("div", { style: { position: "sticky", bottom: 4, zIndex: 3, padding: 8, marginTop: 8, borderRadius: 10, background: "rgba(9,22,38,.97)", border: "1px solid rgba(102,192,244,.28)" } }, h("div", { style: { fontSize: 10, fontWeight: 760, marginBottom: 5 } }, `${fmChosen.length} selected`), h("div", { style: { display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 5 } }, h(MiniButton, { onClick: () => fmStage("copy") }, "Copy"), h(MiniButton, { onClick: () => fmStage("move") }, "Move"), h(MiniButton, { onClick: () => { if (fmChosen.length === 1) {
                setFmRename(fmChosen[0]);
                setFmRenameValue(fmChosen[0].name);
            }
            else
                setErr("Rename: select one item"); } }, "Rename"), h(MiniButton, { onClick: () => fmChosen.length === 1 ? fmDetails(fmChosen[0]) : setErr("Details: select one item") }, "Details"), h(MiniButton, { onClick: () => { if (fmChosen.length === 1 && fmChosen[0].type === "file")
                selectFile(fmChosen[0].path);
            else
                setErr("Share: select one file"); } }, "Share"), h(MiniButton, { onClick: fmTrash, tone: "danger" }, fmTrashArmed ? "Tap again" : "Trash"))))), h(AccordionCard, { icon: "image", tone: "blue", title: "Screenshots", sub: "Pick pictures and send them to your phone", badge: shotPicked.length ? shotPicked.length : null, open: openSections.shots, onToggle: () => toggleSection("shots") }, shots === null ? h("div", { style: { opacity: .55, fontSize: 12, padding: "4px 0" } }, "Looking for screenshots…") :
            !shots.length ? h("div", { style: { fontSize: 11, opacity: .62, lineHeight: 1.4, padding: "2px 0" } }, "No screenshots yet. Press STEAM + R1 in a game to take one.") :
                h("div", null, status.shared && status.shared.length > 0 && h("div", { style: { display: "flex", alignItems: "center", gap: 7, padding: "7px 9px", marginBottom: 8, borderRadius: 9, background: "rgba(61,220,132,.08)", border: "1px solid rgba(61,220,132,.25)", color: "#a8ecc6", fontSize: 10, lineHeight: 1.35 } }, h(Icon, { name: "check", size: 12 }), h("span", { style: { flex: 1 } }, `${status.shared.length} on your phone under Get from Deck`), h(MiniButton, { compact: true, onClick: clearShared }, "Stop sharing")), (() => {
                    const visible = shots.slice(0, shotLimit), groups = [];
                    for (const it of visible) {
                        const g = groups[groups.length - 1];
                        if (g && g.appid === it.appid)
                            g.items.push(it);
                        else
                            groups.push({ appid: it.appid, items: [it] });
                    }
                    return groups.map((g, gi) => h("div", { key: g.appid + "-" + gi }, h("div", { style: { fontSize: 10, fontWeight: 760, opacity: .7, margin: gi ? "10px 2px 5px" : "0 2px 5px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } }, clipGameName(g.appid)), Array.from({ length: Math.ceil(g.items.length / 3) }, (_, r) => h(Focusable, { key: r, "flow-children": "horizontal", style: { display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 5, marginBottom: 5 } }, g.items.slice(r * 3, r * 3 + 3).map(it => {
                        const on = shotPicked.includes(it.id);
                        return h(DialogButton, { key: it.id, onClick: () => toggleShot(it.id), style: { position: "relative", minWidth: 0, minHeight: 0, padding: 0, margin: 0, borderRadius: 8, overflow: "hidden", border: on ? "2px solid #66c0f4" : "2px solid transparent", background: "rgba(255,255,255,.04)", aspectRatio: "16 / 10" } }, shotThumbs[it.id] ? h("img", { src: shotThumbs[it.id], style: { width: "100%", height: "100%", objectFit: "cover", display: "block", opacity: on ? .75 : 1 } }) : h("div", { style: { width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#7cc4ff" } }, h(Icon, { name: "image", size: 16 })), on && h("div", { style: { position: "absolute", top: 3, right: 3, width: 18, height: 18, borderRadius: "50%", background: "#1a9fff", color: "#06121f", display: "flex", alignItems: "center", justifyContent: "center" } }, h(Icon, { name: "check", size: 12, strokeWidth: 3 })));
                    })))));
                })(), shots.length > shotLimit && h(DialogButton, { onClick: () => setShotLimit(x => x + 12), style: { width: "100%", padding: "7px", marginTop: 4, borderRadius: 9, border: "1px solid rgba(120,180,255,.16)", background: "rgba(255,255,255,.025)", color: "#bde7ff", fontSize: 10, fontWeight: 700 } }, `Show more • ${shotLimit} of ${shots.length}`), h("div", { style: { display: "grid", gridTemplateColumns: shotPicked.length ? "minmax(0,1fr) 64px" : "1fr", gap: 6, marginTop: 8 } }, h(DialogButton, { disabled: !shotPicked.length, onClick: sendShots, style: { minHeight: 0, padding: "9px 10px", borderRadius: 10, border: "1px solid rgba(102,192,244,.4)", background: shotPicked.length ? "#1a9fff" : "rgba(255,255,255,.04)", color: shotPicked.length ? "#06121f" : "#8ea2b8", fontSize: 12, fontWeight: 800, textAlign: "center" } }, shotPicked.length ? `Send ${shotPicked.length} to phone` : "Tap pictures to select"), shotPicked.length > 0 && h(MiniButton, { block: true, onClick: () => setShotPicked([]) }, "Clear")))), h(AccordionCard, { icon: "film", tone: "pink", title: "Game clips", sub: "Any length, straight to your phone", open: openSections.clips, onToggle: () => toggleSection("clips") }, clips === null ? h("div", { style: { opacity: .55, fontSize: 12, padding: "4px 0" } }, "Looking for game recordings…") :
            !clips.length ? h("div", { style: { fontSize: 11, opacity: .62, lineHeight: 1.4, padding: "2px 0" } }, "No clips found. Record in a game (Steam button › Game Recording), save a clip, then come back here.") :
                h("div", null, clips.slice(0, clipLimit).map((c, i) => {
                    const job = status.clip_export && status.clip_export.id === c.id ? status.clip_export : null;
                    const working = job && job.state === "working";
                    const ready = job && job.state === "done" && status.selected && status.selected.path === job.path;
                    return h(DialogButton, { key: c.id, onClick: () => working ? null : exportClip(c), style: { width: "100%", minHeight: 0, padding: "6px 7px", margin: "3px 0", borderRadius: 10, border: ready ? "1px solid rgba(61,220,132,.45)" : "1px solid rgba(255,255,255,.07)", background: ready ? "rgba(61,220,132,.08)" : "rgba(255,255,255,.035)", color: "white", textAlign: "left" } }, h("div", { style: { display: "grid", gridTemplateColumns: "64px minmax(0,1fr)", gap: 9, alignItems: "center" } }, clipThumbs[c.id] ? h("img", { src: clipThumbs[c.id], style: { width: 64, height: 36, objectFit: "cover", borderRadius: 6, display: "block" } }) : h("div", { style: { width: 64, height: 36, borderRadius: 6, background: "rgba(255,120,160,.10)", color: "#ff9dbb", display: "flex", alignItems: "center", justifyContent: "center" } }, h(Icon, { name: "film", size: 16 })), h("div", { style: { minWidth: 0 } }, h("div", { style: { fontSize: 11, fontWeight: 740, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } }, clipGameName(c.appid)), h("div", { style: { fontSize: 9, opacity: .55, marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } }, clipMeta(c)), working && h("div", { style: { fontSize: 9, color: "#ffc0d3", marginTop: 3 } }, `Preparing for phone… ${Math.floor(job.percent || 0)}%`), ready && h("div", { style: { display: "flex", alignItems: "center", gap: 4, fontSize: 9, fontWeight: 750, color: "#7fe3ad", marginTop: 3 } }, h(Icon, { name: "check", size: 11 }), "Ready • open Get from Deck on your phone"), job && job.state === "error" && h("div", { style: { fontSize: 9, color: "#ff9a9a", marginTop: 3 } }, job.error || "Failed"))), working && h(Bar, { value: job.percent }));
                }), status.clip_export && status.clip_export.state === "working" && h(MiniButton, { onClick: cancelClipExport, tone: "danger" }, "Stop preparing"), clips.length > clipLimit && h(DialogButton, { onClick: () => setClipLimit(x => x + 8), style: { width: "100%", padding: "7px", marginTop: 5, borderRadius: 9, border: "1px solid rgba(120,180,255,.16)", background: "rgba(255,255,255,.025)", color: "#bde7ff", fontSize: 10, fontWeight: 700 } }, `Show more • ${clipLimit} of ${clips.length}`), h("div", { style: { fontSize: 9, opacity: .45, lineHeight: 1.4, marginTop: 7 } }, "Tap a clip: DeckyShare turns it into an MP4 (same quality) and offers it on your phone under Get from Deck. A copy is kept in Videos/Steam Clips."), h(MiniButton, { onClick: loadClips }, clipBusy ? "Refreshing…" : "Refresh"))), h(AccordionCard, { icon: "clipboard", tone: "amber", title: "Clipboard", sub: "Copy and paste between phone and Deck", badge: status.texts && status.texts.length ? status.texts.length : null, open: openSections.texts, onToggle: () => toggleSection("texts") }, h(Focusable, { "flow-children": "horizontal", style: { display: "grid", gridTemplateColumns: "minmax(0,1fr) 54px 54px", gap: 5, alignItems: "center" } }, h(TextField, { uncontrolled: true, inputRef: composeRef, debugLog: String(status.version || "").includes("-rc") ? logInput : undefined, onChange: e => setTextDraft(e.target.value), placeholder: "Type text or a link for your phone", style: { minWidth: 0, width: "100%", boxSizing: "border-box", padding: "9px 10px", borderRadius: 10, border: "1px solid rgba(255,190,90,.22)", background: "rgba(7,17,29,.48)", color: "white", fontSize: 11, outline: "none" } }), h(MiniButton, { block: true, onClick: pasteFromDeck }, pasteBusy ? "…" : "Paste"), h(MiniButton, { block: true, onClick: sendText }, textBusy ? "…" : "Send")), String(status.version || "").includes("-rc") && inputLog.length > 0 && h("div", { style: { margin: "6px 0 2px", padding: "5px 7px", borderRadius: 7, background: "rgba(0,0,0,.35)", fontFamily: "monospace", fontSize: 8.5, lineHeight: 1.35, color: "#c9d6e3" } }, h("div", { style: { opacity: .6, marginBottom: 2 } }, "Paste test (test builds only)"), inputLog.map((l, i) => h("div", { key: i }, l))), h("div", { style: { fontSize: 9, opacity: .5, lineHeight: 1.45, margin: "6px 1px 4px" } }, "Copy puts text on the Deck clipboard. Paste here fills the box from it. In other apps, tap Paste on the Steam keyboard. On your phone, use the Text tab."), (!status.texts || !status.texts.length) ? h("div", { style: { opacity: .5, fontSize: 11, padding: "8px 0 2px" } }, "Nothing shared yet") :
            h("div", null, status.texts.slice(0, textLimit).map(t => h("div", { key: t.id, style: { background: "rgba(255,255,255,.035)", border: "1px solid rgba(255,255,255,.06)", borderRadius: 11, padding: "8px 9px", margin: "6px 0" } }, h("div", { style: { fontSize: 11, lineHeight: 1.4, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: "5.6em", overflow: "hidden", color: t.link ? "#9ed6ff" : "white" } }, t.text), h("div", { style: { fontSize: 9, opacity: .5, marginTop: 4 } }, `${t.from === "Deck" ? "From this Deck" : `From ${t.from}`} · ${timeAgo(t.at)}`), h(Focusable, { "flow-children": "horizontal", style: { display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 5, marginTop: 7 } }, h(MiniButton, { compact: true, block: true, onClick: () => typeOnDeck(t) }, typingLocal ? "Typing…" : status.typing && status.typing.state === "waiting" ? "Get ready…" : (status.typing && status.typing.state === "typing" ? `Typing ${status.typing.done}/${status.typing.total}` : "Type on Deck")), h(MiniButton, { compact: true, block: true, onClick: () => copyClipboardItem(t) }, copiedPath === t.text ? "✓ Copied" : "Copy")), h(Focusable, { "flow-children": "horizontal", style: { display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 5, marginTop: 5 } }, t.link && h(MiniButton, { compact: true, block: true, onClick: () => openLink(t.text) }, "Open link"), h(MiniButton, { compact: true, block: true, tone: "danger", onClick: () => deleteText(t.id) }, "Delete")), pasteHint === t.id && h("div", { style: { display: "flex", gap: 6, alignItems: "flex-start", marginTop: 7, padding: "6px 8px", borderRadius: 8, background: "rgba(61,220,132,.08)", border: "1px solid rgba(61,220,132,.25)", color: "#a8ecc6", fontSize: 9.5, lineHeight: 1.4 } }, h(Icon, { name: "check", size: 12 }), h("span", null, h("b", null, "Copied. "), "In another app, tap ", h("b", null, "Paste"), " on the Steam keyboard.")))), status.texts.length > textLimit && h(DialogButton, { onClick: () => setTextLimit(x => x + 6), style: { width: "100%", padding: "7px", marginTop: 4, borderRadius: 9, border: "1px solid rgba(120,180,255,.16)", background: "rgba(255,255,255,.025)", color: "#bde7ff", fontSize: 10, fontWeight: 700 } }, `Show more • ${textLimit} of ${status.texts.length}`), status.texts.length > 1 && h("div", { style: { marginTop: 6 } }, h(MiniButton, { tone: "danger", onClick: clearTexts }, clearArmed ? "Press again to clear all" : "Clear all")))), h(AccordionCard, { icon: "inbox", tone: "green", title: "Received files", sub: "Saved in Downloads/DeckShare", badge: status.received && status.received.length ? status.received.length : null, open: openSections.received, onToggle: () => toggleSection("received") }, (!status.received || !status.received.length) ? h("div", { style: { opacity: .5, fontSize: 12, padding: "4px 0" } }, "No received files yet") : status.received.map(f => h("div", { key: f.path, style: { background: "rgba(255,255,255,.035)", border: "1px solid rgba(255,255,255,.06)", borderRadius: 12, padding: 10, margin: "7px 0" } }, h("div", { style: { display: "flex", gap: 9, alignItems: "center" } }, h("div", { style: { width: 34, height: 34, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(26,159,255,.12)", color: "#7cc4ff" } }, browseFileIcon(f, 18)), h("div", { style: { minWidth: 0, flex: 1 } }, h("div", { style: { fontWeight: 740, wordBreak: "break-word" } }, f.name), h("div", { style: { fontSize: 10, opacity: .54, marginTop: 2 } }, f.size_human))), h("div", { style: { fontSize: 9, opacity: .42, marginTop: 6, wordBreak: "break-all" } }, f.path), h("div", { style: { display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" } }, h(MiniButton, { onClick: () => showReceivedFolder(f.path) }, "Show folder"), h(MiniButton, { onClick: () => copyText(f.path, "Path") }, copiedPath === f.path ? "✓ Copied" : "Copy path"), h(MiniButton, { onClick: () => deleteReceived(f.path), tone: "danger" }, deleteArmed === f.path ? "Tap again" : "Delete"))))), busy && h(DialogButton, { onClick: () => setShowQr(v => !v), style: { width: "100%", minHeight: 0, margin: "8px 0", padding: "11px 12px", borderRadius: 14, border: "1px solid rgba(255,255,255,.07)", background: "rgba(19,28,39,.96)", color: "white", textAlign: "left" } }, h("div", { style: { display: "flex", alignItems: "center", gap: 9 } }, h(IconTile, { name: "qr", tone: "gray" }), h("span", { style: { fontWeight: 760, fontSize: 14 } }, showQr ? "Hide QR code" : "Show QR code"))), !busy && h(RecentList, { items: status.received }), !busy && h("div", { style: { fontSize: 10, fontWeight: 800, letterSpacing: .9, textTransform: "uppercase", opacity: .45, margin: "16px 4px 4px" } }, "More"), !busy && h(AccordionCard, { icon: "wifi", tone: "gray", title: "Wi-Fi", sub: null, meta: wifiSummary(wifi), open: openSections.wifi, onToggle: () => { const opening = !openSections.wifi; toggleSection("wifi"); if (opening)
                loadWifi(); } }, !wifi ? h("div", { style: { opacity: .6, fontSize: 12, padding: "4px 0" } }, wifiBusy ? "Checking…" : "Checking Deck Wi-Fi…") :
            wifi.error ? h("div", { style: { fontSize: 12, color: "#ffb4a8", padding: "4px 0" } }, wifi.error) :
                h("div", null, wifiRows(wifi).map(([k, v]) => h("div", { key: k, style: { display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, padding: "2px 0" } }, h("span", { style: { opacity: .62 } }, k), h("span", { style: { fontWeight: 650, textAlign: "right", wordBreak: "break-word" } }, v))), (wifi.hints || []).map((t, i) => h("div", { key: "hint" + i, style: { fontSize: 11, lineHeight: 1.35, marginTop: 6, padding: "6px 8px", borderRadius: 8, background: "rgba(102,192,244,.10)", border: "1px solid rgba(102,192,244,.25)" } }, t))), h("div", { style: { marginTop: 8 } }, h(MiniButton, { onClick: loadWifi, compact: true }, wifiBusy ? "Checking…" : "Refresh"))), !busy && h(AccordionCard, { icon: "update", tone: "gray", title: "Updates", sub: null, meta: updateMeta(updateInfo), open: openSections.updates, onToggle: () => toggleSection("updates") }, h("div", { style: { fontSize: 11, opacity: .68, lineHeight: 1.45, marginBottom: 8 } }, updateInfo && updateInfo.current ? `Installed: v${updateInfo.current}` : (status.version ? `Installed: v${status.version}` : "")), updateInfo && updateInfo.installed_now && h("div", { style: { padding: "9px", borderRadius: 10, background: "rgba(70,210,125,.10)", border: "1px solid rgba(80,220,140,.18)", fontSize: 11, lineHeight: 1.45, marginBottom: 8 } }, `✓ ${updateInfo.installed} installed safely. Reload DeckyShare from Decky settings to finish.`), updateInfo && updateInfo.ok && updateInfo.latest && updateInfo.available && h("div", { style: { padding: "9px", borderRadius: 10, background: "rgba(71,142,230,.10)", border: "1px solid rgba(100,180,255,.18)", marginBottom: 8 } }, h("div", { style: { fontWeight: 760, fontSize: 12 } }, `v${updateInfo.latest} available`), h("div", { style: { fontSize: 10, opacity: .6, marginTop: 3 } }, `${fmt(updateInfo.asset_size || 0)} • SHA-256 verified by GitHub`), updateInfo.notes && h("div", { style: { fontSize: 10, opacity: .68, whiteSpace: "pre-wrap", maxHeight: 72, overflow: "hidden", marginTop: 6 } }, updateInfo.notes)), updateInfo && updateInfo.ok && updateInfo.latest && updateInfo.same && h("div", { style: { fontSize: 11, opacity: .68, marginBottom: 8 } }, `✓ You're on the latest stable release (v${updateInfo.latest}).`), updateInfo && updateInfo.ok && updateInfo.latest && updateInfo.ahead && h("div", { style: { fontSize: 11, opacity: .68, marginBottom: 8 } }, `Development build detected. Latest stable release is v${updateInfo.latest}.`), updateInfo && !updateInfo.ok && updateInfo.error && h("div", { style: { fontSize: 11, color: "#ffb3b3", marginBottom: 8, wordBreak: "break-word" } }, updateInfo.error), h("div", { style: { display: "flex", gap: 6, flexWrap: "wrap" } }, h(MiniButton, { onClick: () => checkUpdate(true) }, updateBusy ? "Working…" : "Check for update"), updateInfo && updateInfo.available && h(MiniButton, { onClick: installUpdate }, updateBusy ? "Installing…" : updateArmed ? `Confirm v${updateInfo.latest}` : `Install v${updateInfo.latest}`), updateInfo && updateInfo.rollback_available && h(MiniButton, { onClick: rollbackUpdate, tone: "danger" }, rollbackArmed ? "Confirm rollback" : "Rollback")), h("div", { style: { fontSize: 9, opacity: .42, lineHeight: 1.35, marginTop: 8 } }, "Updates use Decky Loader’s native installer. GitHub SHA-256 is verified and Decky asks before replacing the plugin.")), !busy && h(AccordionCard, { icon: "settings", tone: "gray", title: "Settings & support", sub: null, open: openSections.support, onToggle: () => toggleSection("support") }, h(SubSection, { title: "Notifications", first: true }, h("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 } }, h("div", { style: { fontSize: 11, opacity: .65, lineHeight: 1.35 } }, notifyOn ? "On • multi-file receives are grouped" : "Notifications are off"), h(MiniButton, { onClick: toggleNotifications }, notifyOn ? "Turn off" : "Turn on"))), h(SubSection, { title: "Support DeckyShare" }, h(DialogButton, { onClick: () => { try {
                window.open("https://buymeacoffee.com/Gillrv", "_blank");
            }
            catch (e) { } }, style: { width: "100%", padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(255,196,92,.30)", background: "rgba(255,183,65,.10)", color: "#ffe0a3", fontWeight: 750 } }, "Buy me a coffee"))), err && h("div", { style: { color: "#ffb3b3", marginTop: 8, fontSize: 11, wordBreak: "break-word" } }, err));
    };
}
function index () {
    const Panel = makePanel();
    let notifyAPI = null, receiveListener = null, textListener = null;
    try {
        notifyAPI = connectDeckyBackend();
        if (notifyAPI && typeof notifyAPI.addEventListener === "function") {
            receiveListener = (...args) => queueReceivedToast(notifyAPI, args.length ? args[args.length - 1] : null);
            notifyAPI.addEventListener("file_received", receiveListener);
            textListener = (...args) => { const t = unwrap(args.length ? args[args.length - 1] : null); if (!t || !t.text || !notificationsEnabled())
                return; const snippet = String(t.text).replace(/\s+/g, " ").slice(0, 60); toast(notifyAPI, `Text from ${t.from || "phone"}: ${snippet}${t.text.length > 60 ? "…" : ""}`); };
            notifyAPI.addEventListener("text_received", textListener);
        }
    }
    catch (e) {
        console.error("[DeckyShare] global receive notifications unavailable", e);
    }
    return {
        name: "DeckyShare",
        titleView: h("div", { style: { display: "flex", alignItems: "center", gap: 8, fontWeight: 700 } }, h(BrandTile, { size: 24 }), "DeckyShare"),
        content: h(Panel),
        icon: h(DeckyShareBrandIcon, { size: 22 }),
        onDismount() {
            try {
                if (notifyAPI && receiveListener && typeof notifyAPI.removeEventListener === "function")
                    notifyAPI.removeEventListener("file_received", receiveListener);
            }
            catch (e) { }
            try {
                if (notifyAPI && textListener && typeof notifyAPI.removeEventListener === "function")
                    notifyAPI.removeEventListener("text_received", textListener);
            }
            catch (e) { }
            if (receivedBatchTimer) {
                clearTimeout(receivedBatchTimer);
                receivedBatchTimer = null;
            }
            receivedBatch = [];
            console.log("DeckyShare UI unloaded");
        }
    };
}

export { index as default };
//# sourceMappingURL=index.js.map
