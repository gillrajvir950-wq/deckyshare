import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path


class _Logger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        decky = types.SimpleNamespace(
            DECKY_USER_HOME=cls.temp.name,
            DECKY_PLUGIN_DIR=str(Path(__file__).resolve().parents[1]),
            DECKY_PLUGIN_SETTINGS_DIR=cls.temp.name,
            DECKY_PLUGIN_RUNTIME_DIR=cls.temp.name,
            logger=_Logger(),
        )
        sys.modules["decky"] = decky
        cls.core = importlib.import_module("core_main")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def make_handler(self, path="/", headers=None, client="192.168.1.50"):
        handler = self.core.Handler.__new__(self.core.Handler)
        handler.path = path
        handler.headers = headers or {}
        handler.client_address = (client, 12345)
        return handler

    def test_missing_token_is_rejected(self):
        self.assertFalse(self.make_handler().token_ok())

    def test_wrong_token_is_rejected(self):
        self.assertFalse(self.make_handler("/?token=wrong").token_ok())

    def test_query_token_is_accepted(self):
        token = self.core.STATE.token
        self.assertTrue(self.make_handler(f"/?token={token}").token_ok())

    def test_cookie_token_is_accepted(self):
        token = self.core.STATE.token
        headers = {"Cookie": f"other=x; deckyshare_token={token}"}
        self.assertTrue(self.make_handler(headers=headers).token_ok())

    def test_loopback_detection(self):
        self.assertTrue(self.make_handler(client="127.0.0.1").loopback_client())
        self.assertTrue(self.make_handler(client="::1").loopback_client())
        self.assertFalse(self.make_handler(client="192.168.1.50").loopback_client())


if __name__ == "__main__":
    unittest.main()
