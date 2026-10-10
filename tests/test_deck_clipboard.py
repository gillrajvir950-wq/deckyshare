"""Deck clipboard reader (deck_clipboard.py): fails cleanly without a display."""
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deck_clipboard  # noqa: E402


class ClipboardTests(unittest.TestCase):
    def test_no_display_returns_reason_quickly(self):
        with mock.patch.object(deck_clipboard, "steam_display_env", return_value={}), \
             mock.patch.dict(os.environ, {"DISPLAY": ":97"}, clear=False), \
             mock.patch.object(deck_clipboard, "_displays", return_value=([":97"], None)):
            start = time.monotonic()
            text, reason = deck_clipboard.read_clipboard()
        self.assertIsNone(text)
        self.assertTrue(reason)
        self.assertLess(time.monotonic() - start, 5)

    def test_steam_env_lookup_does_not_crash(self):
        self.assertIsInstance(deck_clipboard.steam_display_env(), dict)


if __name__ == "__main__":
    unittest.main()
