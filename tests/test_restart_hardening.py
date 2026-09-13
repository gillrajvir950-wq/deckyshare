import tempfile
import time
import unittest
from pathlib import Path

from restart_hardening import cleanup_orphan_parts, zero_byte_download_headers


class RestartHardeningTests(unittest.TestCase):
    def test_stale_upload_part_is_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            part = Path(tmp) / ".deckyshare-abcdefgh.part"
            part.write_bytes(b"partial")
            old = time.time() - (25 * 60 * 60)
            import os
            os.utime(part, (old, old))
            removed = cleanup_orphan_parts(tmp, now=time.time())
            self.assertIn(part.name, removed)
            self.assertFalse(part.exists())

    def test_recent_upload_part_survives_restart_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            part = Path(tmp) / ".deckyshare-abcdefgh.part"
            part.write_bytes(b"partial")
            removed = cleanup_orphan_parts(tmp, now=time.time())
            self.assertEqual(removed, [])
            self.assertTrue(part.exists())

    def test_zero_byte_headers(self):
        headers = zero_byte_download_headers('empty.txt', 'text/plain')
        self.assertEqual(headers['Content-Length'], '0')
        self.assertEqual(headers['Accept-Ranges'], 'bytes')
        self.assertIn('empty.txt', headers['Content-Disposition'])


if __name__ == '__main__':
    unittest.main()
