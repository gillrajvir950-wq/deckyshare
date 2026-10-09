import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


class _Logger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class SenderDeviceTests(unittest.TestCase):
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

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_user_agents_map_to_devices(self):
        d = self.core.device_from_user_agent
        self.assertEqual(d("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit"), "iPhone")
        self.assertEqual(d("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X)"), "iPad")
        self.assertEqual(d("Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/126"), "Android")
        self.assertEqual(d("okhttp/4.12.0"), "Android")
        self.assertEqual(d("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605"), "Mac")
        self.assertEqual(d("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"), "Windows PC")
        self.assertEqual(d("Mozilla/5.0 (X11; Linux x86_64) Firefox/128"), "Linux PC")
        self.assertEqual(d("BackgroundShortcutRunner/1.0"), "iPhone")
        self.assertIsNone(d(""))

    def test_sender_log_persists_and_is_bounded(self):
        log_path = Path(self.temp.name) / "received_from.json"
        log = self.core.SenderLog()
        log.path = log_path
        log.remember("a.mov", "iPhone")
        log.remember("b.zip", None)  # unknown senders are not stored
        self.assertEqual(log.get("a.mov"), "iPhone")
        self.assertIsNone(log.get("b.zip"))
        self.assertEqual(json.loads(log_path.read_text())["a.mov"], "iPhone")
        for i in range(self.core.SenderLog.LIMIT + 10):
            log.remember(f"f{i}", "Mac")
        self.assertLessEqual(len(log.items), self.core.SenderLog.LIMIT)


if __name__ == "__main__":
    unittest.main()
