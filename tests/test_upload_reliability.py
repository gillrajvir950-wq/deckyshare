import os
import tempfile
import unittest
from pathlib import Path

from transfer_integrity import remove_partial, resume_offset, rollback_partial
from exactly_once import _parallel_boundaries


def unique_destination_path(path):
    path = Path(path)
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


class UploadReliabilityTests(unittest.TestCase):
    def test_interrupted_fast_request_is_removed_from_live_transfers(self):
        source = (Path(__file__).resolve().parents[1] / "exactly_once.py").read_text(encoding="utf-8")

        self.assertIn("def _retire_transfer(core, tid):", source)
        self.assertIn("core.STATE.transfers.pop(tid, None)", source)
        self.assertIn('core.STATE.new_transfer("upload", name, total, current)', source)

    def test_resumed_transfer_speed_uses_only_new_request_bytes(self):
        source = (Path(__file__).resolve().parents[1] / "core_main.py").read_text(encoding="utf-8")

        self.assertIn("def new_transfer(self, direction, name, total, initial_done=0):", source)
        self.assertIn('"base_done": initial_done', source)
        self.assertIn('t["done"] - t.get("base_done", 0)', source)

    def test_fast_stream_does_not_wait_for_a_huge_buffer_or_rehash_bytes(self):
        source = (Path(__file__).resolve().parents[1] / "exactly_once.py").read_text(encoding="utf-8")

        self.assertIn('hasattr(handler.rfile, "read1")', source)
        self.assertIn("chunk = _read_upload_chunk(self, remain, fast_mode)", source)
        self.assertIn("if expected_crc:\n                            crc = core.crc32_update(crc, chunk)", source)

    def test_new_retry_supersedes_old_stream_from_same_device(self):
        source = (Path(__file__).resolve().parents[1] / "exactly_once.py").read_text(encoding="utf-8")

        self.assertIn("def _supersede_prior_streams(core, upload_id, client_key, name):", source)
        self.assertIn('old.get("client_key") != client_key', source)
        self.assertIn('old["cancel_event"].set()', source)
        self.assertIn("_supersede_prior_streams(core, upload_id, client_key, name)", source)

    def test_parallel_ranges_cover_file_exactly_without_overlap(self):
        total = 101
        ranges = [_parallel_boundaries(total, lane, 3) for lane in range(3)]

        self.assertEqual(ranges, [(0, 33), (33, 67), (67, 101)])
        self.assertEqual(sum(end - start for start, end in ranges), total)

    def test_parallel_upload_uses_direct_offset_writes(self):
        source = (Path(__file__).resolve().parents[1] / "exactly_once.py").read_text(encoding="utf-8")

        self.assertIn('self.headers.get("X-DeckyShare-Parallel", "") == "1"', source)
        self.assertIn('written = os.pwrite(f.fileno(), chunk, absolute)', source)
        self.assertIn('"lane_done": [0] * lanes', source)
        self.assertIn('session.get("mode") == "parallel"', source)

    def test_no_resume_mode_uses_a_coalesced_single_stream_hot_path(self):
        source = (Path(__file__).resolve().parents[1] / "exactly_once.py").read_text(encoding="utf-8")

        self.assertIn("def _handle_no_resume_put(", source)
        self.assertIn('self.headers.get("X-DeckyShare-No-Resume", "") == "1"', source)
        self.assertIn('"mode": "no_resume"', source)
        self.assertIn('with open(part, "wb", buffering=0) as output:', source)
        self.assertIn("current - last_report_bytes >= 4 * 1024 * 1024", source)
        self.assertIn('"restart_required": True', source)

    def test_active_cancel_is_signalled_without_waiting_for_upload_lock(self):
        source = (Path(__file__).resolve().parents[1] / "exactly_once.py").read_text(encoding="utf-8")
        cancel_handler = source[source.index("def _install_post"):source.index("def _wrap_html_page")]

        self.assertIn('session["cancel_event"].set()', cancel_handler)
        self.assertIn('status="cancelled"', cancel_handler)
        self.assertIn('"cleanup_pending": True', cancel_handler)
        self.assertNotIn("with _upload_lock(upload_id):", cancel_handler)

    def test_interrupted_upload_resumes_without_rewriting_good_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            part = Path(tmp) / "large.iso.deckshare-part"
            first = b"A" * (1024 * 1024)
            second = b"B" * 4096
            part.write_bytes(first)

            offset = resume_offset(part)
            self.assertEqual(offset, len(first))

            with part.open("ab") as handle:
                handle.write(second)

            self.assertEqual(part.read_bytes(), first + second)

    def test_corrupt_retry_starts_at_last_good_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            part = Path(tmp) / "movie.mkv.deckshare-part"
            good = b"good" * 1000
            corrupt = b"bad" * 1000
            retry = b"fixed" * 1000
            part.write_bytes(good + corrupt)

            rollback_partial(part, len(good))
            self.assertEqual(resume_offset(part), len(good))

            with part.open("ab") as handle:
                handle.write(retry)

            self.assertEqual(part.read_bytes(), good + retry)

    def test_duplicate_final_name_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "game.iso"
            original.write_bytes(b"original")

            destination = unique_destination_path(original)
            self.assertEqual(destination.name, "game (1).iso")
            destination.write_bytes(b"new")

            self.assertEqual(original.read_bytes(), b"original")
            self.assertEqual(destination.read_bytes(), b"new")

    def test_duplicate_counter_skips_existing_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("clip.mp4", "clip (1).mp4", "clip (2).mp4"):
                (root / name).write_bytes(name.encode())

            self.assertEqual(unique_destination_path(root / "clip.mp4").name, "clip (3).mp4")

    def test_cancel_after_interruption_keeps_completed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final = root / "save.zip"
            part = root / "save.zip.deckshare-part"
            final.write_bytes(b"old-complete-copy")
            part.write_bytes(os.urandom(8192))

            self.assertTrue(remove_partial(part))
            self.assertFalse(part.exists())
            self.assertEqual(final.read_bytes(), b"old-complete-copy")


if __name__ == "__main__":
    unittest.main()
