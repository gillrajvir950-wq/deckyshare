import os
import tempfile
import unittest
from pathlib import Path

from transfer_integrity import remove_partial, resume_offset, rollback_partial


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
