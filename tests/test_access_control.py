"""v1.3.1 access control: secrets kept out of logs, no phone-side file browsing,
revocation of remembered devices and of the Share Sheet / Android app key."""
import asyncio
import http.cookiejar
import importlib
import json
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path


class _Logger:
    def __init__(self):
        self.lines = []

    def __getattr__(self, _name):
        return lambda msg="", *a, **k: self.lines.append(str(msg))


class AccessControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        if "decky" not in sys.modules:
            sys.modules["decky"] = types.SimpleNamespace(
                DECKY_USER_HOME=cls.temp.name,
                DECKY_PLUGIN_DIR=str(Path(__file__).resolve().parents[1]),
                DECKY_PLUGIN_SETTINGS_DIR=cls.temp.name,
                DECKY_PLUGIN_RUNTIME_DIR=cls.temp.name,
                logger=_Logger(),
            )
        cls.core = importlib.import_module("core_main")
        cls.log = _Logger()
        cls.old_logger = cls.core.decky.logger
        cls.core.decky.logger = cls.log
        cls.plugin = cls.core.Plugin()
        asyncio.run(cls.plugin.bootstrap())
        cls.base = f"http://127.0.0.1:{cls.core.STATE.port}"

    @classmethod
    def tearDownClass(cls):
        cls.core.decky.logger = cls.old_logger
        cls.temp.cleanup()

    def opener(self):
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar

    def get(self, opener, path, data=None, headers=None):
        req = urllib.request.Request(self.base + path, data=data, headers=headers or {})
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    # --- logs -------------------------------------------------------------
    def test_redact_secrets(self):
        r = self.core.redact_secrets
        self.assertEqual(r('"GET /?token=abc123 HTTP/1.1" 200 -'), '"GET /?token=*** HTTP/1.1" 200 -')
        self.assertEqual(r("POST /shortcut/share?key=SeCrEt&name=a.jpg"), "POST /shortcut/share?key=***&name=a.jpg")
        self.assertEqual(r("POST /shortcut/pair?code=123456"), "POST /shortcut/pair?code=***")
        self.assertEqual(r("GET /download?i=2 HTTP/1.1"), "GET /download?i=2 HTTP/1.1")

    def test_session_token_never_reaches_the_log(self):
        token = self.core.STATE.token
        op, _ = self.opener()
        self.get(op, f"/?token={token}")
        self.get(op, f"/api/status?token={token}")
        joined = "\n".join(self.log.lines)
        self.assertIn("token=***", joined)
        self.assertNotIn(token, joined)

    # --- endpoints ----------------------------------------------------------
    def test_phone_cannot_browse_or_pick_deck_files(self):
        token = self.core.STATE.token
        op, _ = self.opener()
        self.assertEqual(self.get(op, f"/api/roots?token={token}")[0], 404)
        self.assertEqual(self.get(op, f"/api/browse?token={token}&path=/")[0], 404)
        secret = Path(self.temp.name) / "private.txt"
        secret.write_text("private")
        body = json.dumps({"path": str(secret)}).encode()
        status, _ = self.get(op, f"/api/select?token={token}", body, {"Content-Type": "application/json"})
        self.assertEqual(status, 403)
        # A file the phone sent itself may still be offered back (benchmark tool).
        mine = self.core.STATE.receive_dir / "sent-by-phone.bin"
        mine.parent.mkdir(parents=True, exist_ok=True)
        mine.write_bytes(b"x" * 10)
        body = json.dumps({"path": str(mine)}).encode()
        status, _ = self.get(op, f"/api/select?token={token}", body, {"Content-Type": "application/json"})
        self.assertEqual(status, 200)

    # --- remembered devices -------------------------------------------------
    def test_forgotten_device_loses_access_immediately(self):
        op, jar = self.opener()
        self.assertEqual(self.get(op, f"/?token={self.core.STATE.token}")[0], 200)
        self.assertIn("deckyshare_device", [c.name for c in jar])
        self.assertEqual(self.get(op, "/api/status")[0], 200)
        self.core.STATE.token = "after-restart-" + self.core.STATE.token  # Deck restart
        self.assertEqual(self.get(op, "/api/status")[0], 200)  # still remembered
        did = [d for d in self.core.DEVICES.list()][0]["id"]
        asyncio.run(self.plugin.forget_device({"id": did}))
        self.assertEqual(self.get(op, "/api/status")[0], 403)  # device key and old session key both dead

    # --- Share Sheet / Android app key -------------------------------------
    def test_share_key_can_be_reset(self):
        key = self.core.STATE.share_key
        op, _ = self.opener()
        status, _ = self.get(op, f"/shortcut/share?key={key}&name=a.txt", b"hello", {"Content-Type": "text/plain"})
        self.assertEqual(status, 200)
        self.assertIsNotNone(asyncio.run(self.plugin.status())["share_key_used"])
        self.assertNotIn(key, "\n".join(self.log.lines))
        asyncio.run(self.plugin.reset_share_key())
        status, _ = self.get(op, f"/shortcut/share?key={key}&name=b.txt", b"hello", {"Content-Type": "text/plain"})
        self.assertEqual(status, 403)
        new = self.core.STATE.share_key
        self.assertNotEqual(new, key)
        status, _ = self.get(op, f"/shortcut/share?key={new}&name=c.txt", b"hello", {"Content-Type": "text/plain"})
        self.assertEqual(status, 200)

    def test_forget_all_also_resets_share_key(self):
        key = self.core.STATE.share_key
        asyncio.run(self.plugin.forget_all_devices())
        self.assertNotEqual(self.core.STATE.share_key, key)
        self.assertEqual(self.core.DEVICES.list(), [])


if __name__ == "__main__":
    unittest.main()
