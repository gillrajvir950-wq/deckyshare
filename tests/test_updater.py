import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from updater import UpdateError, UpdateManager, compare_versions, validate_update_zip


def make_plugin(root: Path, version: str, marker: str):
    root.mkdir(parents=True, exist_ok=True)
    (root / "dist").mkdir(exist_ok=True)
    (root / "plugin.json").write_text(json.dumps({"name": "DeckyShare", "author": "test", "api_version": 1}))
    (root / "package.json").write_text(json.dumps({"name": "deckyshare", "version": version}))
    (root / "main.py").write_text(f"MARKER = {marker!r}\n")
    (root / "dist" / "index.js").write_text("export default function(){return {};};\n" * 20)


def make_zip(path: Path, version: str, marker: str):
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "DeckyShare"
        make_plugin(src, version, marker)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in src.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(src.parent))
    return hashlib.sha256(path.read_bytes()).hexdigest()


class VersionTests(unittest.TestCase):
    def test_semver_ordering(self):
        self.assertGreater(compare_versions("1.1.0-rc.1", "1.0.0"), 0)
        self.assertLess(compare_versions("1.1.0-rc.1", "1.1.0"), 0)
        self.assertEqual(compare_versions("1.1.0-rc1", "1.1.0-rc.1"), 0)
        self.assertGreater(compare_versions("2.0.0", "1.99.99"), 0)

    def test_release_check_chooses_highest_semver_not_first_api_item(self):
        releases = []
        for version in ("1.1.0-rc.11.9", "1.1.0-rc.11.10", "1.1.0-rc.11.8"):
            releases.append({
                "tag_name": f"v{version}",
                "name": f"DeckyShare {version}",
                "draft": False,
                "prerelease": True,
                "assets": [{
                    "name": f"DeckyShare-v{version}.zip",
                    "browser_download_url": f"https://github.com/gillrajvir950-wq/deckyshare/releases/download/v{version}/DeckyShare-v{version}.zip",
                    "size": 1234,
                    "digest": "sha256:" + "a" * 64,
                }],
            })
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plugin_dir = root / "DeckyShare"
            make_plugin(plugin_dir, "1.1.0-rc.11.9", "old")
            manager = UpdateManager(plugin_dir, root / "home")
            with mock.patch("updater._http_json", return_value=releases) as request:
                release = manager._fetch_release(include_prerelease=True)
            self.assertEqual(release["version"], "1.1.0-rc.11.10")
            self.assertIn("per_page=100", request.call_args.args[0])


class ArchiveTests(unittest.TestCase):
    def test_valid_archive(self):
        with tempfile.TemporaryDirectory() as td:
            z = Path(td) / "DeckyShare-v1.2.0.zip"
            make_zip(z, "1.2.0", "new")
            self.assertEqual(validate_update_zip(z, "1.2.0"), Path("DeckyShare"))

    def test_zip_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            z = Path(td) / "bad.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("DeckyShare/plugin.json", json.dumps({"name": "DeckyShare"}))
                zf.writestr("DeckyShare/package.json", json.dumps({"version": "1.2.0"}))
                zf.writestr("DeckyShare/main.py", "x=1\n")
                zf.writestr("DeckyShare/dist/index.js", "x" * 300)
                zf.writestr("DeckyShare/../escape.txt", "bad")
            with self.assertRaises(UpdateError):
                validate_update_zip(z, "1.2.0")


class InstallTests(unittest.TestCase):
    def test_prepare_install_hands_verified_asset_to_decky(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            plugin_dir = base / "plugins" / "DeckyShare"
            user_home = base / "home"
            make_plugin(plugin_dir, "1.1.0-rc.11.8", "old")
            user_home.mkdir()
            manager = UpdateManager(plugin_dir, user_home)
            manager._fetch_release = lambda include_prerelease=False: {
                "tag": "v1.1.0-rc.11.9",
                "version": "1.1.0-rc.11.9",
                "asset": {
                    "url": "https://github.com/gillrajvir950-wq/deckyshare/releases/download/v1.1.0-rc.11.9/DeckyShare-v1.1.0-rc.11.9.zip",
                    "sha256": "a" * 64,
                },
            }
            result = manager.prepare_install("v1.1.0-rc.11.9", True)
            self.assertTrue(result["ok"])
            self.assertTrue(result["request_install"])
            self.assertEqual(result["installer"], "decky-loader")
            self.assertEqual(result["sha256"], "a" * 64)
            self.assertEqual(json.loads((plugin_dir / "package.json").read_text())["version"], "1.1.0-rc.11.8")

    def test_atomic_install_and_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            plugin_dir = base / "plugins" / "DeckyShare"
            user_home = base / "home"
            plugin_dir.parent.mkdir(parents=True)
            user_home.mkdir()
            make_plugin(plugin_dir, "1.1.0", "old")

            archive = base / "DeckyShare-v1.2.0.zip"
            digest = make_zip(archive, "1.2.0", "new")
            manager = UpdateManager(plugin_dir, user_home)
            result = manager.install_archive(archive, "1.2.0", digest)
            self.assertTrue(result["ok"])
            self.assertEqual(json.loads((plugin_dir / "package.json").read_text())["version"], "1.2.0")
            self.assertIn("new", (plugin_dir / "main.py").read_text())
            state = manager.state()
            self.assertTrue(state["rollback_available"])
            self.assertEqual(state["previous_version"], "1.1.0")

            rolled = manager.rollback()
            self.assertTrue(rolled["ok"])
            self.assertEqual(json.loads((plugin_dir / "package.json").read_text())["version"], "1.1.0")
            self.assertIn("old", (plugin_dir / "main.py").read_text())

    def test_bad_digest_does_not_touch_live_plugin(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            plugin_dir = base / "plugins" / "DeckyShare"
            user_home = base / "home"
            plugin_dir.parent.mkdir(parents=True)
            user_home.mkdir()
            make_plugin(plugin_dir, "1.1.0", "old")
            archive = base / "DeckyShare-v1.2.0.zip"
            make_zip(archive, "1.2.0", "new")
            manager = UpdateManager(plugin_dir, user_home)
            with self.assertRaises(UpdateError):
                manager.install_archive(archive, "1.2.0", "0" * 64)
            self.assertEqual(json.loads((plugin_dir / "package.json").read_text())["version"], "1.1.0")
            self.assertIn("old", (plugin_dir / "main.py").read_text())


if __name__ == "__main__":
    unittest.main()
