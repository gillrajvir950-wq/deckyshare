"""ROMs into EmuDeck / RetroDECK folders (rom_sort.py)."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rom_sort  # noqa: E402


def make_iso(path, marker=b"", offset=0x8000, magic_at=None, magic=b""):
    data = bytearray(64 * 1024)
    if marker:
        data[offset:offset + len(marker)] = marker
    if magic_at is not None:
        data[magic_at:magic_at + len(magic)] = magic
    path.write_bytes(bytes(data))
    return path


class DetectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.d = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_extensions(self):
        self.assertEqual(rom_sort.detect_system(Path("Pokemon Emerald.GBA")), "Game Boy Advance")
        self.assertEqual(rom_sort.detect_system(Path("zelda.nsp")), "Switch")
        self.assertEqual(rom_sort.detect_system(Path("mario.z64")), "Nintendo 64")
        self.assertIsNone(rom_sort.detect_system(Path("game.chd")))
        self.assertIsNone(rom_sort.detect_system(Path("game.zip")))
        self.assertIsNone(rom_sort.detect_system(Path("holiday.mp4")))

    def test_disc_images(self):
        ps2 = make_iso(self.d / "a.iso", b"SYSTEM.CNF;1 BOOT2 = cdrom0:\\SLUS_200.62;1")
        psp = make_iso(self.d / "b.iso", b"PSP GAME")
        ps1 = make_iso(self.d / "c.iso", b"PLAYSTATION BOOT = cdrom:\\SCUS_941.63;1")
        gc = make_iso(self.d / "d.iso", magic_at=0x1C, magic=rom_sort.GC_MAGIC)
        wii = make_iso(self.d / "e.iso", magic_at=0x18, magic=rom_sort.WII_MAGIC)
        other = make_iso(self.d / "f.iso", b"just a data disc")
        rvz = self.d / "g.rvz"
        rvz.write_bytes(b"RVZ\x01" + b"\0" * (0x48 - 4) + (2).to_bytes(4, "big") + b"\0" * 64)
        self.assertEqual(rom_sort.detect_system(ps2), "PlayStation 2")
        self.assertEqual(rom_sort.detect_system(psp), "PSP")
        self.assertEqual(rom_sort.detect_system(ps1), "PlayStation")
        self.assertEqual(rom_sort.detect_system(gc), "GameCube")
        self.assertEqual(rom_sort.detect_system(wii), "Wii")
        self.assertEqual(rom_sort.detect_system(rvz), "Wii")
        self.assertIsNone(rom_sort.detect_system(other))


class SorterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "home"
        self.roms = self.home / "Emulation" / "roms"
        for name in ("gba", "ps2", "n3ds", "switch"):
            (self.roms / name).mkdir(parents=True)
        self.inbox = self.home / "Downloads" / "DeckShare"
        self.inbox.mkdir(parents=True)
        self.settings = Path(self.temp.name) / "settings"
        self.sorter = rom_sort.RomSorter(self.home, self.settings)
        self.media = mock.patch.object(rom_sort, "Path", wraps=Path)  # keep real Path

    def tearDown(self):
        self.temp.cleanup()

    def wait(self, path, timeout=5):
        end = time.time() + timeout
        while time.time() < end and not self.sorter.recent_moves():
            time.sleep(0.02)

    def test_moves_rom_into_existing_folder(self):
        f = self.inbox / "Pokemon.gba"
        f.write_bytes(b"x" * 1000)
        done = []
        job = self.sorter.maybe_sort(f, "iPhone", delay=0, on_done=done.append)
        self.assertEqual(job["system"], "Game Boy Advance")
        self.wait(f)
        self.assertFalse(f.exists())
        self.assertTrue((self.roms / "gba" / "Pokemon.gba").is_file())
        move = self.sorter.recent_moves()[0]
        self.assertEqual((move["system"], move["app"], move["from"]), ("Game Boy Advance", "EmuDeck", "iPhone"))
        self.assertEqual(done[0]["path"], str(self.roms / "gba" / "Pokemon.gba"))
        # remembered after a restart
        again = rom_sort.RomSorter(self.home, self.settings)
        self.assertEqual(len(again.recent_moves()), 1)

    def test_alternative_folder_name(self):
        f = self.inbox / "Zelda.3ds"
        f.write_bytes(b"x")
        self.sorter.maybe_sort(f, delay=0)
        self.wait(f)
        self.assertTrue((self.roms / "n3ds" / "Zelda.3ds").is_file())

    def test_no_folder_or_unknown_or_disabled_stays(self):
        nds = self.inbox / "game.nds"  # no nds folder exists
        nds.write_bytes(b"x")
        self.assertIsNone(self.sorter.maybe_sort(nds, delay=0))
        chd = self.inbox / "game.chd"
        chd.write_bytes(b"x")
        self.assertIsNone(self.sorter.maybe_sort(chd, delay=0))
        self.sorter.set_enabled(False)
        gba = self.inbox / "b.gba"
        gba.write_bytes(b"x")
        self.assertIsNone(self.sorter.maybe_sort(gba, delay=0))
        self.assertTrue(nds.exists() and chd.exists() and gba.exists())
        self.assertFalse(rom_sort.RomSorter(self.home, self.settings).enabled)

    def test_existing_name_gets_number_and_cross_drive_copy(self):
        (self.roms / "switch" / "Mario.nsp").write_bytes(b"old")
        f = self.inbox / "Mario.nsp"
        f.write_bytes(b"new" * 100)
        real_replace = os.replace
        calls = []

        def fake_replace(a, b):
            calls.append((a, b))
            if len(calls) == 1:
                raise OSError(18, "Invalid cross-device link")
            return real_replace(a, b)

        with mock.patch.object(rom_sort.os, "replace", side_effect=fake_replace):
            self.sorter.maybe_sort(f, delay=0)
            self.wait(f)
        self.assertEqual((self.roms / "switch" / "Mario.nsp").read_bytes(), b"old")
        self.assertEqual((self.roms / "switch" / "Mario (1).nsp").read_bytes(), b"new" * 100)
        self.assertFalse(f.exists())
        self.assertFalse(any(p.name.startswith(".deckyshare-moving") for p in (self.roms / "switch").iterdir()))

    def test_retrodeck_used_when_no_emudeck(self):
        home = Path(self.temp.name) / "home2"
        (home / "retrodeck" / "roms" / "psx").mkdir(parents=True)
        folder, app = rom_sort.target_folder(home, "PlayStation")
        self.assertEqual((folder.name, app), ("psx", "RetroDECK"))


if __name__ == "__main__":
    unittest.main()
