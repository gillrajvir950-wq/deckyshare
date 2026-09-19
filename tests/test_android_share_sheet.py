import threading
from pathlib import Path

from share_sheet import pair_request, start_pairing


class PairState:
    def __init__(self):
        self.lock = threading.RLock()
        self.shortcut_pairing_code = None
        self.shortcut_pairing_expires = 0.0
        self.shortcut_pairing_attempts = {}


def test_android_pairing_code_exchanges_for_authenticated_endpoint():
    state = PairState()
    started = start_pairing(state, "http://192.168.1.20:8787")
    assert started["active"] is True
    result, status = pair_request(
        state,
        {"code": [started["code"]]},
        "192.168.1.30",
        "http://192.168.1.20:8787",
        "secret-key-for-tests-123456",
    )
    assert status == 200
    assert result["endpoint"].startswith("http://192.168.1.20:8787/shortcut/share?")
    assert "key=" in result["endpoint"]
    assert state.shortcut_pairing_code is None


def test_android_app_registers_single_and_multiple_share_targets():
    root = Path(__file__).resolve().parents[1]
    manifest = (root / "android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    activity = (root / "android/app/src/main/java/com/deckyshare/android/MainActivity.java").read_text(encoding="utf-8")
    assert "android.intent.action.SEND" in manifest
    assert "android.intent.action.SEND_MULTIPLE" in manifest
    assert "setFixedLengthStreamingMode(item.size)" in activity
    assert "byte[] buffer = new byte[1024 * 1024]" in activity
    assert "readAllBytes" not in activity


def test_backend_exposes_pair_and_share_routes_before_session_auth():
    root = Path(__file__).resolve().parents[1]
    source = (root / "core_main.py").read_text(encoding="utf-8")
    pair = source.index('if u.path == "/shortcut/pair"')
    share = source.index('if u.path == "/shortcut/share"')
    token = source.index("if not self.token_ok():", pair)
    assert pair < token
    assert share < token
