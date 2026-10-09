import importlib
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path


class _Logger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class DeckCancelTests(unittest.TestCase):
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
        self.core.STATE.transfers.clear()
        self.core.STATE.cancel_tids.clear()
        self.core.STATE.upload_sessions = {}

    def test_inactive_transfer_cannot_be_cancelled(self):
        self.assertFalse(self.core.cancel_transfer_by_id("missing")["ok"])

    def test_download_cancel_stops_all_copies_and_sharing(self):
        state = self.core.STATE
        state.selected = Path(self.temp.name) / "movie.mp4"
        a = state.new_transfer("download", "movie.mp4", 100)
        b = state.new_transfer("download", "movie.mp4", 100)
        other = state.new_transfer("download", "other.mp4", 100)
        result = self.core.cancel_transfer_by_id(a)
        self.assertTrue(result["ok"])
        self.assertIn(a, state.cancel_tids)
        self.assertIn(b, state.cancel_tids)
        self.assertNotIn(other, state.cancel_tids)
        self.assertIsNone(state.selected)

    def test_upload_cancel_signals_session_and_blocks_retries(self):
        state = self.core.STATE
        tid = state.new_transfer("upload", "clip.mov", 100)
        session = {"tid": tid, "name": "clip.mov", "cancel_event": threading.Event()}
        state.upload_sessions["a" * 32] = session
        result = self.core.cancel_transfer_by_id(tid)
        self.assertTrue(result["ok"])
        self.assertTrue(session["cancel_event"].is_set())
        self.assertTrue(session["deck_cancel"])
        self.assertIn("a" * 32, state.deck_cancelled_uploads)
        self.assertEqual(state.transfers[tid]["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
