import unittest

from transfer_integrity import crc32_update, crc32_value_hex


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


if __name__ == "__main__":
    unittest.main()
