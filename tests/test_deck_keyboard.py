"""Typing text on the Deck through a virtual keyboard (deck_keyboard.py)."""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deck_keyboard as kb  # noqa: E402

# Reverse map so tests can turn key presses back into text.
_BACK = {(code, False): ch for ch, code in kb._PLAIN.items()}
_BACK.update({(code, True): ch for ch, code in kb._SHIFTED.items()})
_BACK.update({(code, True): ch.upper() for ch, code in kb._PLAIN.items() if ch.isalpha()})


class FakeKeyboard:
    instances = []

    def __init__(self):
        self.taps = []
        self.closed = False
        FakeKeyboard.instances.append(self)

    def tap(self, code, shift=False, gap=0):
        self.taps.append((code, shift))

    def close(self):
        self.closed = True

    def text(self):
        return "".join(_BACK.get(t, "?") for t in self.taps)


def wait(typist, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        job = typist.snapshot()
        if job and job["state"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise AssertionError("typing did not finish")


class PlanTests(unittest.TestCase):
    def test_round_trip_ascii(self):
        text = "Hello, World! user@mail.com #42 (a+b)=c_d ~/x|y? <tag> {k:\"v\"} 'q' `z` ^&*%$\\"
        keys, skipped = kb.plan_keys(text)
        self.assertEqual(skipped, 0)
        self.assertEqual("".join(_BACK[k] for k in keys), text)

    def test_newlines_and_smart_quotes(self):
        keys, skipped = kb.plan_keys("one\ntwo \u201cok\u201d \u2014 \u00fc")
        self.assertEqual("".join(_BACK[k] for k in keys), 'one two "ok" - ')
        self.assertEqual(skipped, 1)
        keys, _ = kb.plan_keys("a\nb", enter_for_newlines=True)
        self.assertIn((kb.KEY_ENTER, False), keys)


class TypistTests(unittest.TestCase):
    def setUp(self):
        FakeKeyboard.instances.clear()
        self.typist = kb.Typist(FakeKeyboard)

    def test_types_text_and_closes_keyboard(self):
        self.typist.start("R7KQ2 m9xpl", delay=0)
        job = wait(self.typist)
        self.assertEqual(job["state"], "done")
        board = FakeKeyboard.instances[0]
        self.assertEqual(board.text(), "R7KQ2 m9xpl")
        self.assertTrue(board.closed)

    def test_refuses_empty_and_too_long(self):
        with self.assertRaises(kb.KeyboardError):
            self.typist.start("   ")
        with self.assertRaises(kb.KeyboardError):
            self.typist.start("x" * (kb.MAX_TYPE_CHARS + 1))
        with self.assertRaises(kb.KeyboardError):
            self.typist.start("\u00fc\u00f6")

    def test_one_job_at_a_time_and_cancel(self):
        self.typist.start("abc", delay=2)
        with self.assertRaises(kb.KeyboardError):
            self.typist.start("def")
        self.typist.stop()
        job = wait(self.typist)
        self.assertEqual(job["state"], "error")
        self.assertEqual(job["error"], "Cancelled")
        self.assertEqual(FakeKeyboard.instances[0].taps, [])

    def test_missing_uinput_is_a_clear_error(self):
        typist = kb.Typist(lambda: kb.VirtualKeyboard("/nonexistent/uinput"))
        typist.start("hi", delay=0)
        job = wait(typist)
        self.assertEqual(job["state"], "error")
        self.assertIn("uinput", job["error"])


if __name__ == "__main__":
    unittest.main()
