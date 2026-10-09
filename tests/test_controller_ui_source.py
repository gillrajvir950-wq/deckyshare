from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sections_use_controller_accordions_except_connect_card():
    source = (ROOT / "src" / "index.tsx").read_text(encoding="utf-8")
    assert 'function AccordionCard(' in source
    assert '"aria-expanded":!!open' in source
    for section in ("browse", "received", "notifications", "updates", "support", "wifi"):
        assert f'open:openSections.{section}' in source
    assert "h(TransferHero,{transfers:status.transfers})" in source
    assert 'title:"Live Transfers"' not in source
    assert 'title:"Connect",sub:"Phone: scan the QR · Computer: address + code"' in source
    assert 'h(Card,{style:{border:"1px solid rgba(66,153,255,.28)"}}' in source


def test_compact_toolbar_and_single_focus_ring():
    source = (ROOT / "src" / "index.tsx").read_text(encoding="utf-8")
    assert source.count("compact:true") >= 3
    assert "shared.noFocusRing=true" in source
    assert "shared.noFocusRing=false" not in source
    assert "shared.onGamepadFocus" not in source
    assert 'boxShadow:"inset 3px 0 0 #66c0f4"' in source
    assert 'filter:"none"' in source
    assert 'transform:"none"' in source
    assert 'className:"deckyshare-compact-action"' in source
    assert '"⋯"' not in source


def test_current_breadcrumb_is_plain_readable_text():
    source = (ROOT / "src" / "index.tsx").read_text(encoding="utf-8")
    assert 'title:path' in source
    assert 'browseCrumbs.map(c=>c.label).join(" › ")||path' in source
