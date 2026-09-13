import tempfile
import unittest
from pathlib import Path

from transfer_integrity import (
    crc32_update,
    crc32_value_hex,
    remove_partial,
    resume_offset,
    rollback_partial,
)


class TransferIntegrityTests(unittest.TestCase):
    def test_known_crc32_vector(self):
        value = crc32_update(0, b"123456789")
        self.assertEqual(crc32_value_hex(value), "cbf43926")

    def test_streaming_matches_single_pass(self):
        data = (b"DeckyShare-" * 500000) + b"end"
        whole = crc32_update(0, data)

        running = 0
        step = 1024 * 1024
        for offset in range(0, len(data), step):
            running = crc32_update(running, data[offset:offset + step])

        self.assertEqual(crc32_value_hex(running), crc32_value_hex(whole))

    def test_hex_output_is_fixed_width(self):
        self.assertEqual(crc32_value_hex(0), "00000000")
        self.assertEqual(len(crc32_value_hex(0xFFFFFFFF)), 8)

    def test_resume_offset_uses_partial_file_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            part = Path(tmp) / "game.iso.deckshare-part"
            self.assertEqual(resume_offset(part), 0)
            part.write_bytes(b"a" * 12345)
            self.assertEqual(resume_offset(part), 12345)

    def test_checksum_failure_can_roll_back_current_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            part = Path(tmp) / "video.mkv.deckshare-part"
            good = b"good-data"
            bad = b"corrupt-chunk"
            part.write_bytes(good + bad)

            rollback_partial(part, len(good))

            self.assertEqual(part.read_bytes(), good)
            self.assertEqual(resume_offset(part), len(good))

    def test_cancel_removes_only_partial_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final = root / "photo.jpg"
            part = root / "photo.jpg.deckshare-part"
            final.write_bytes(b"already-complete")
            part.write_bytes(b"unfinished")

            self.assertTrue(remove_partial(part))
            self.assertFalse(part.exists())
            self.assertEqual(final.read_bytes(), b"already-complete")
            self.assertFalse(remove_partial(part))


if __name__ == "__main__":
    unittest.main()
