import unittest

from notification_state import NotificationDeduper


class NotificationDeduperTests(unittest.TestCase):
    def test_same_received_file_is_suppressed_inside_ttl(self):
        dedupe = NotificationDeduper(ttl_seconds=4)
        item = {"name": "game.iso", "path": "/tmp/game.iso"}

        self.assertTrue(dedupe.should_notify("received", item, now=10))
        self.assertFalse(dedupe.should_notify("received", item, now=12))
        self.assertTrue(dedupe.should_notify("received", item, now=15))

    def test_different_files_are_not_suppressed(self):
        dedupe = NotificationDeduper(ttl_seconds=4)

        self.assertTrue(dedupe.should_notify("received", {"path": "/tmp/a"}, now=1))
        self.assertTrue(dedupe.should_notify("received", {"path": "/tmp/b"}, now=1.5))

    def test_event_type_is_part_of_identity(self):
        dedupe = NotificationDeduper(ttl_seconds=4)
        item = {"path": "/tmp/a"}

        self.assertTrue(dedupe.should_notify("received", item, now=1))
        self.assertTrue(dedupe.should_notify("failed", item, now=1.1))

    def test_clear_allows_notification_again(self):
        dedupe = NotificationDeduper(ttl_seconds=4)
        item = {"path": "/tmp/a"}

        self.assertTrue(dedupe.should_notify("received", item, now=1))
        self.assertFalse(dedupe.should_notify("received", item, now=2))
        dedupe.clear()
        self.assertTrue(dedupe.should_notify("received", item, now=2.1))


if __name__ == "__main__":
    unittest.main()
