import errno
import unittest

from exactly_once import _storage_error


class StorageErrorTests(unittest.TestCase):
    def test_enospc_maps_to_507(self):
        status, code, message = _storage_error(OSError(errno.ENOSPC, "No space left on device"))
        self.assertEqual(status, 507)
        self.assertEqual(code, "storage_full")
        self.assertIn("storage", message.lower())

    def test_generic_oserror_maps_to_500(self):
        status, code, message = _storage_error(OSError(errno.EIO, "I/O error"))
        self.assertEqual(status, 500)
        self.assertEqual(code, "write_failed")
        self.assertIn("save", message.lower())


if __name__ == "__main__":
    unittest.main()
