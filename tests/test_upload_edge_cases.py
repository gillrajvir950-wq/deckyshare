import tempfile
import unittest
from pathlib import Path

from transfer_integrity import create_empty_file, parse_nonnegative_int, validate_upload_window


class UploadEdgeCaseTests(unittest.TestCase):
    def test_zero_byte_upload_is_valid(self):
        validate_upload_window(0, 0, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "empty.txt"
            create_empty_file(target)
            self.assertTrue(target.exists())
            self.assertEqual(target.stat().st_size, 0)

    def test_empty_file_creation_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "empty.txt"
            target.write_bytes(b"keep-me")
            with self.assertRaises(FileExistsError):
                create_empty_file(target)
            self.assertEqual(target.read_bytes(), b"keep-me")

    def test_negative_numbers_are_rejected(self):
        for field in ("offset", "total", "length"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    parse_nonnegative_int(-1, field)

    def test_malformed_numbers_are_rejected(self):
        for value in (None, "", "1.5", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_nonnegative_int(value, "offset")

    def test_chunk_cannot_exceed_declared_total(self):
        with self.assertRaisesRegex(ValueError, "Chunk exceeds"):
            validate_upload_window(8, 10, 3, 8)

    def test_partial_file_cannot_exceed_declared_total(self):
        with self.assertRaisesRegex(ValueError, "Partial file exceeds"):
            validate_upload_window(12, 10, 0, 12)

    def test_resume_offset_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Resume offset mismatch"):
            validate_upload_window(4, 10, 2, 3)

    def test_valid_large_file_window(self):
        gib = 1024 * 1024 * 1024
        total = 100 * gib
        current = 63 * gib
        length = 4 * 1024 * 1024
        validate_upload_window(current, total, length, current)


if __name__ == "__main__":
    unittest.main()
