"""Shared clipboard between phone/PC and Deck (text_share.py)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import text_share  # noqa: E402
import web_ui  # noqa: E402


class TextBoardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "texts.json"
        self.board = text_share.TextBoard(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_add_newest_first_and_persisted(self):
        self.board.add("first", "iPhone")
        self.board.add("second", "Deck")
        self.assertEqual([i["text"] for i in self.board.snapshot()], ["second", "first"])
        again = text_share.TextBoard(self.path)
        self.assertEqual([i["text"] for i in again.snapshot()], ["second", "first"])

    def test_same_text_moves_to_top(self):
        self.board.add("a", "iPhone")
        self.board.add("b", "iPhone")
        self.board.add("a", "Deck")
        items = self.board.snapshot()
        self.assertEqual([i["text"] for i in items], ["a", "b"])
        self.assertEqual(items[0]["from"], "Deck")

    def test_limits(self):
        with self.assertRaises(ValueError):
            self.board.add("   ", "iPhone")
        with self.assertRaises(ValueError):
            self.board.add("x" * (text_share.MAX_CHARS + 1), "iPhone")
        for n in range(text_share.MAX_ITEMS + 5):
            self.board.add(f"item {n}", "iPhone")
        self.assertEqual(len(self.board.snapshot()), text_share.MAX_ITEMS)

    def test_only_http_links_are_links(self):
        self.assertTrue(self.board.add("https://example.com/a?b=1", "iPhone")["link"])
        self.assertFalse(self.board.add("javascript:alert(1)", "iPhone")["link"])
        self.assertFalse(self.board.add("see https://example.com", "iPhone")["link"])
        self.assertFalse(self.board.add("https://a.com\nhttps://b.com", "iPhone")["link"])

    def test_delete_and_clear(self):
        item = self.board.add("bye", "iPhone")
        self.board.add("stay", "iPhone")
        self.assertTrue(self.board.delete(item["id"]))
        self.assertFalse(self.board.delete("missing"))
        self.assertEqual([i["text"] for i in self.board.snapshot()], ["stay"])
        self.board.clear()
        self.assertEqual(self.board.snapshot(), [])

    def test_corrupt_file_is_ignored(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(text_share.TextBoard(self.path).snapshot(), [])


class PhonePageTests(unittest.TestCase):
    def test_text_tab_present_and_escaped(self):
        page = web_ui.html_page("http://192.168.1.2:8787/")
        self.assertIn('id="tab-text"', page)
        self.assertIn('id="panel-text"', page)
        self.assertIn("linkify(t.text)", page)  # text goes through escapeHtml first


if __name__ == "__main__":
    unittest.main()
