"""Release notes for the panel, read from the CHANGELOG.md bundled with the plugin."""
from __future__ import annotations

import re
from pathlib import Path

_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def clean_line(line: str) -> str:
    """Markdown bullet/line -> plain text for the Deck panel."""
    s = line.strip()
    s = re.sub(r"^[-*+]\s+", "", s)
    s = re.sub(r"^#+\s*", "", s)
    s = _LINK.sub(r"\1", s)
    s = s.replace("**", "").replace("__", "").replace("`", "")
    return s.strip()


def _base(version: str) -> str:
    return str(version or "").lstrip("v").split("-", 1)[0]


def notes_for(changelog_text: str, version: str, limit: int = 12):
    """Plain-text lines of the section for `version` (falls back to its base version)."""
    sections = {}
    current = None
    for raw in changelog_text.splitlines():
        m = re.match(r"^##\s+v?(\S+)", raw)
        if m:
            current = m.group(1)
            sections[current] = []
            continue
        if current is not None and raw.strip():
            sections[current].append(raw)
    wanted = str(version or "").lstrip("v")
    lines = sections.get(wanted)
    if lines is None:
        lines = sections.get(_base(wanted))
        if lines is not None:
            wanted = _base(wanted)
    if lines is None:
        return {"version": str(version or ""), "lines": []}
    out = []
    for raw in lines:
        if raw.lstrip().startswith("###"):
            continue
        text = clean_line(raw)
        if text:
            out.append({"text": text, "bullet": bool(re.match(r"^\s*[-*+]\s", raw))})
    return {"version": wanted, "lines": out[:limit]}


def installed_notes(plugin_dir, version: str):
    try:
        text = (Path(plugin_dir) / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        return {"version": str(version or ""), "lines": []}
    return notes_for(text, version)
