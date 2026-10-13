"""Remembered devices (trusted_devices.py)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import trusted_devices as td  # noqa: E402


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "devices.json"
        self.store = td.DeviceStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_create_verify_and_persist(self):
        cookie = self.store.create("iPhone")
        self.assertEqual(self.store.verify(cookie)["name"], "iPhone")
        self.assertNotIn(cookie.split(".", 1)[1], self.path.read_text())  # only a hash is stored
        self.assertEqual(td.DeviceStore(self.path).verify(cookie)["name"], "iPhone")

    def test_wrong_or_malformed_cookie(self):
        cookie = self.store.create("Mac")
        did = cookie.split(".")[0]
        for bad in ("", "nodot", did + ".wrongsecret", "ffffffffffff." + cookie.split(".", 1)[1]):
            self.assertIsNone(self.store.verify(bad), bad)

    def test_forget(self):
        a, b = self.store.create("A"), self.store.create("B")
        self.assertTrue(self.store.forget(a.split(".")[0]))
        self.assertIsNone(self.store.verify(a))
        self.assertIsNotNone(self.store.verify(b))
        self.store.forget_all()
        self.assertIsNone(self.store.verify(b))
        self.assertEqual(self.store.list(), [])

    def test_limit(self):
        cookies = [self.store.create(f"D{i}") for i in range(td.LIMIT + 3)]
        self.assertEqual(len(self.store.list()), td.LIMIT)
        self.assertIsNotNone(self.store.verify(cookies[-1]))

    def test_cookie_header(self):
        h = td.cookie_header("abc.def")
        self.assertIn("HttpOnly", h)
        self.assertIn("SameSite=Lax", h)
        self.assertIn("Max-Age=", h)


if __name__ == "__main__":
    unittest.main()
