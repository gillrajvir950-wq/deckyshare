#!/usr/bin/env python3
"""Apply the RC11.5 controller-navigation patch to an RC11.4 package."""

from __future__ import annotations

import json
import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: rc11_5_patch.py PATH_TO_DECKYSHARE")

    root = pathlib.Path(sys.argv[1])
    ui_path = root / "dist" / "index.js"
    package_path = root / "package.json"
    ui = ui_path.read_text(encoding="utf-8")

    ui = replace_once(
        ui,
        'const { useEffect, useMemo, useRef, useState } = React;\n',
        'const { useEffect, useMemo, useRef, useState } = React;\n'
        'const DeckyUI = window.DFL || {};\n'
        'const DialogButton = DeckyUI.DialogButton || "button";\n'
        'const Focusable = DeckyUI.Focusable || "div";\n'
        'const TextField = DeckyUI.TextField || "input";\n',
        "Decky UI component setup",
    )

    # Steam's gamepad navigation recognises Decky UI controls, not arbitrary DOM
    # buttons/inputs. Keep the existing styling and handlers while changing the
    # rendered control primitives.
    ui = ui.replace('h("button",', 'h(DialogButton,')
    ui = ui.replace('h("input",', 'h(TextField,')

    ui = replace_once(
        ui,
        '    const lastReceivedRef=useRef(null);\n'
        '    const transferStatesRef=useRef(new Map());',
        '    const lastReceivedRef=useRef(null);\n'
        '    const transferStatesRef=useRef(new Map());\n'
        '    const firstBrowseItemRef=useRef(null);',
        "browse focus ref",
    )

    marker = '    async function selectFile(p){try{await call("select_file",{path:p});await refreshStatus();}catch(e){setErr("Selection: "+String(e&&e.message||e));}}'
    navigation = '''    function leaveBrowser(){
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
'''
    ui = replace_once(ui, marker, navigation + marker, "controller back handler")

    ui = replace_once(
        ui,
        '    useEffect(()=>{bootstrap();},[]);\n'
        '    useEffect(()=>{if(!status)return;const t=setInterval(refreshStatus,path?4000:1500);return()=>clearInterval(t);},[!!status,!!path]);',
        '    useEffect(()=>{bootstrap();},[]);\n'
        '    useEffect(()=>{if(!status)return;const t=setInterval(refreshStatus,path?4000:1500);return()=>clearInterval(t);},[!!status,!!path]);\n'
        '    useEffect(()=>{if(!path||status&&status.selected)return;const t=setTimeout(()=>{try{if(firstBrowseItemRef.current&&typeof firstBrowseItemRef.current.focus==="function")firstBrowseItemRef.current.focus();}catch(e){}},80);return()=>clearTimeout(t);},[path,items,status&&status.selected]);',
        "initial browse focus",
    )

    ui = replace_once(
        ui,
        '    return h("div",{style:{padding:"4px 8px 18px",fontSize:14,color:"white"}},',
        '    return h(Focusable,{onCancel:handleControllerBack,style:{padding:"4px 8px 18px",fontSize:14,color:"white"}},',
        "controller focus root",
    )

    ui = replace_once(
        ui,
        'h("span",{style:{fontSize:8,fontWeight:800,padding:"1px 5px",borderRadius:999,background:"rgba(80,160,255,.16)",border:"1px solid rgba(100,180,255,.24)",color:"#9fd4ff"}},"RC11.4")',
        'h("span",{style:{fontSize:8,fontWeight:800,padding:"1px 5px",borderRadius:999,background:"rgba(80,160,255,.16)",border:"1px solid rgba(100,180,255,.24)",color:"#9fd4ff"}},"RC11.5")',
        "RC badge",
    )

    ui = replace_once(
        ui,
        '          h("div",{style:{display:"grid",gridTemplateColumns:"1fr auto",gap:6,alignItems:"center",marginBottom:7}},\n'
        '            h("div",{style:{display:"flex",gap:3,alignItems:"center",minWidth:0,overflow:"hidden",padding:"6px 7px",borderRadius:9,background:"rgba(7,17,29,.34)",border:"1px solid rgba(120,180,255,.10)"}},',
        '          h("div",{style:{display:"grid",gridTemplateColumns:"auto minmax(0,1fr) auto",gap:6,alignItems:"center",marginBottom:7}},\n'
        '            h(DialogButton,{onClick:navigateBack,style:{width:38,height:34,minWidth:38,padding:0,margin:0,borderRadius:9,border:"1px solid rgba(120,180,255,.16)",background:"rgba(255,255,255,.025)",color:"#d9edff",fontSize:18,fontWeight:800}},"←"),\n'
        '            h("div",{style:{display:"flex",gap:3,alignItems:"center",minWidth:0,overflow:"hidden",padding:"6px 7px",borderRadius:9,background:"rgba(7,17,29,.34)",border:"1px solid rgba(120,180,255,.10)"}},',
        "visible back button",
    )

    ui = replace_once(
        ui,
        'visibleBrowseItems.slice(0,browseLimit).map(it=>h(DialogButton,{key:it.path,onClick:',
        'visibleBrowseItems.slice(0,browseLimit).map((it,index)=>h(DialogButton,{key:it.path,ref:index===0?firstBrowseItemRef:null,onClick:',
        "first row focus target",
    )

    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = "1.1.0-rc.11.5"
    package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    ui_path.write_text(ui, encoding="utf-8")

    print("RC11.5 controller navigation patch applied")


if __name__ == "__main__":
    main()
