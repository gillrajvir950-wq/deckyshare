"""Steam game recording clips -> MP4 (steam_clips.py)."""
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import steam_clips  # noqa: E402

FFMPEG = shutil.which("ffmpeg")


def _make_clip(home: Path, name: str, first: int, last: int, extra_video_args=()):
    """Record a Steam-like DASH session with ffmpeg and keep segments first..last, like a Steam clip."""
    src = home / "src" / name
    src.mkdir(parents=True)
    subprocess.run(
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x200:rate=30",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "20",
         "-c:v", "libx264", "-preset", "ultrafast", "-g", "60", *extra_video_args, "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-f", "dash", "-seg_duration", "2", str(src / "session.mpd")],
        check=True, capture_output=True)
    clip = home / ".local/share/Steam/userdata/42/gamerecordings/clips" / name
    video = clip / "video" / "fg_42_20261001_115900"
    video.mkdir(parents=True)
    for f in src.glob("init-*"):
        shutil.copy(f, video)
    for f in src.glob("chunk-*"):
        if first <= int(f.stem.split("-")[-1]) <= last:
            shutil.copy(f, video)
    return clip


class NameTests(unittest.TestCase):
    def test_output_name_uses_game_and_time(self):
        name = steam_clips.output_name(Path("clip_2208920_20260913_045426"), "Elden Ring: Nightreign")
        self.assertEqual(name, "Elden Ring Nightreign 2026-09-13 04-54-26.mp4")

    def test_output_name_without_game(self):
        self.assertEqual(steam_clips.output_name(Path("clip_7_20260101_000000")), "Steam clip 7 2026-01-01 00-00-00.mp4")

    def test_safe_name_strips_paths(self):
        self.assertNotIn("/", steam_clips.safe_name("../../etc/passwd"))

    def test_elst_round_trip(self):
        payload = steam_clips._elst([(1000, -1), (5000, 512)])
        self.assertEqual(payload[4:8], b"elst")
        self.assertEqual(struct.unpack(">I", payload[12:16])[0], 2)


@unittest.skipUnless(FFMPEG, "ffmpeg not installed")
class RemuxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.home = Path(cls.temp.name)
        cls.clip = _make_clip(cls.home, "clip_2208920_20260913_045426", 3, 7)
        cls.clip_b = _make_clip(cls.home, "clip_1245620_20261001_101500", 1, 10, ("-preset", "fast", "-bf", "2"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def _probe(self, path):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
                              "-of", "csv=p=0", str(path)], check=True, capture_output=True, text=True).stdout
        return [line.split(",") for line in out.split()]

    def test_list_clips(self):
        clips = steam_clips.list_clips(self.home)
        self.assertEqual([c["appid"] for c in clips], ["1245620", "2208920"])
        by_id = {c["appid"]: c for c in clips}
        self.assertAlmostEqual(by_id["2208920"]["seconds"], 10.0, delta=0.1)
        self.assertAlmostEqual(by_id["1245620"]["seconds"], 20.0, delta=0.1)

    def test_is_clip_dir_rejects_other_folders(self):
        self.assertTrue(steam_clips.is_clip_dir(self.clip, self.home))
        self.assertFalse(steam_clips.is_clip_dir(self.home / "src", self.home))
        self.assertFalse(steam_clips.is_clip_dir(Path("/etc"), self.home))

    def test_remux_is_playable_with_audio_and_video(self):
        for clip, seconds in ((self.clip, 10.0), (self.clip_b, 20.0)):
            out = self.home / "out" / (clip.name + ".mp4")
            info = steam_clips.remux_clip(clip, out)
            self.assertAlmostEqual(info["seconds"], seconds, delta=0.1)
            streams = dict(self._probe(out))
            self.assertIn("video", streams)
            self.assertIn("audio", streams)
            subprocess.run([FFMPEG, "-v", "error", "-xerror", "-i", str(out), "-f", "null", "-"], check=True)
            head = out.read_bytes()[:64]
            self.assertEqual(head[4:8], b"ftyp")
            self.assertEqual(head[36:40], b"moov")  # fast start: index before the media data
            self.assertFalse(any(p.name.endswith(".part") for p in out.parent.iterdir()))

    def test_exporter_reuses_finished_file(self):
        exporter = steam_clips.ClipExporter()
        done = []
        out_dir = self.home / "Videos" / "Steam Clips"
        exporter.start(self.clip, out_dir, "Test Game", done.append)
        for _ in range(100):
            if done:
                break
            import time
            time.sleep(0.05)
        self.assertEqual(done[0]["state"], "done")
        again = exporter.start(self.clip, out_dir, "Test Game")
        self.assertTrue(again.get("reused"))
        self.assertTrue((out_dir / "Test Game 2026-09-13 04-54-26.mp4").is_file())


if __name__ == "__main__":
    unittest.main()
