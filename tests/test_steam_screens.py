"""Steam screenshots listing and validation (steam_screens.py)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import steam_screens  # noqa: E402


class ScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        base = self.home / ".local/share/Steam/userdata/42/760/remote"
        self.a = base / "1245620" / "screenshots"
        self.b = base / "2208920" / "screenshots"
        (self.a / "thumbnails").mkdir(parents=True)
        self.b.mkdir(parents=True)
        for d, name in ((self.a, "20261001120000_1.jpg"), (self.a, "20261003090000_1.jpg"), (self.b, "20261002100000_1.png")):
            (d / name).write_bytes(b"\xff\xd8\xff" + b"x" * 100)
        (self.a / "thumbnails" / "20261001120000_1.jpg").write_bytes(b"\xff\xd8\xffthumb")
        (self.a / "notes.txt").write_text("not a picture")

    def tearDown(self):
        self.temp.cleanup()

    def test_lists_newest_first_across_games(self):
        items = steam_screens.list_screenshots(self.home)
        self.assertEqual([i["name"] for i in items], ["20261003090000_1.jpg", "20261002100000_1.png", "20261001120000_1.jpg"])
        self.assertEqual(items[1]["appid"], "2208920")
        self.assertTrue(items[2]["has_thumbnail"])
        self.assertFalse(items[0]["has_thumbnail"])

    def test_is_screenshot(self):
        self.assertTrue(steam_screens.is_screenshot(self.a / "20261001120000_1.jpg", self.home))
        self.assertFalse(steam_screens.is_screenshot(self.a / "notes.txt", self.home))
        self.assertFalse(steam_screens.is_screenshot(self.a / "thumbnails" / "20261001120000_1.jpg", self.home))
        outside = self.home / "screenshots" / "x.jpg"
        outside.parent.mkdir()
        outside.write_bytes(b"\xff\xd8\xff")
        self.assertFalse(steam_screens.is_screenshot(outside, self.home))

    def test_thumbnail_falls_back_to_picture(self):
        with_thumb = self.a / "20261001120000_1.jpg"
        without = self.a / "20261003090000_1.jpg"
        self.assertEqual(steam_screens.thumbnail_path(with_thumb).parent.name, "thumbnails")
        self.assertEqual(steam_screens.thumbnail_path(without), without)


if __name__ == "__main__":
    unittest.main()
