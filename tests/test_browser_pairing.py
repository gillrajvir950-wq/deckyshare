import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path


class _Logger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class BrowserPairingTests(unittest.TestCase):
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

    def setUp(self):
        state = self.core.STATE
        state.browser_pair_code = None
        state.browser_pair_expires = 0.0
        state.browser_pair_attempts = {}
        state.browser_pair_failures = []

    def wrong_code(self, code):
        return "000000" if code != "000000" else "111111"

    def test_code_is_six_digits_and_stable_until_used(self):
        first = self.core.browser_pair_info()
        second = self.core.browser_pair_info()
        self.assertRegex(first["code"], r"^\d{6}$")
        self.assertEqual(first["code"], second["code"])
        self.assertGreater(first["expires_in"], 500)

    def test_right_code_works_once(self):
        code = self.core.browser_pair_info()["code"]
        status, _ = self.core.browser_pair_check("10.0.0.2", code[:3] + " " + code[3:])
        self.assertEqual(status, 200)
        status, _ = self.core.browser_pair_check("10.0.0.2", code)
        self.assertEqual(status, 410)
        self.assertNotEqual(self.core.browser_pair_info()["code"], None)

    def test_wrong_code_is_rejected_and_rate_limited(self):
        code = self.core.browser_pair_info()["code"]
        bad = self.wrong_code(code)
        statuses = [self.core.browser_pair_check("10.0.0.3", bad)[0] for _ in range(7)]
        self.assertEqual(statuses[:6], [403] * 6)
        self.assertEqual(statuses[6], 429)
        # Even the right code is refused while that client is rate limited.
        self.assertEqual(self.core.browser_pair_check("10.0.0.3", code)[0], 429)
        # Another client is unaffected.
        self.assertEqual(self.core.browser_pair_check("10.0.0.4", code)[0], 200)

    def test_too_many_wrong_codes_overall_rotate_the_code(self):
        code = self.core.browser_pair_info()["code"]
        bad = self.wrong_code(code)
        for i in range(self.core.BROWSER_PAIR_MAX_TOTAL):
            self.core.browser_pair_check(f"10.1.{i}.1", bad)
        self.assertEqual(self.core.browser_pair_check("10.2.0.1", code)[0], 410)

    def test_expired_code_is_rejected(self):
        code = self.core.browser_pair_info()["code"]
        self.core.STATE.browser_pair_expires = 0.0
        self.assertEqual(self.core.browser_pair_check("10.0.0.5", code)[0], 410)

    def test_pair_page_is_self_contained(self):
        page = importlib.import_module("web_ui").pair_page_html()
        self.assertIn('fetch(\'/pair\'', page)
        self.assertIn('autocomplete="one-time-code"', page)
        self.assertNotIn("http://", page.replace('xmlns="http://www.w3.org/2000/svg"', ""))


if __name__ == "__main__":
    unittest.main()
