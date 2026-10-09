import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


class UpdaterModuleCollisionTests(unittest.TestCase):
    def test_decky_loader_updater_name_cannot_shadow_plugin_updater(self):
        repo = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            r'''
            import importlib.util
            import pathlib
            import sys
            import tempfile
            import types

            plugin_dir = pathlib.Path(sys.argv[1])
            home = pathlib.Path(tempfile.mkdtemp(prefix="deckyshare-collision-"))

            foreign = types.ModuleType("updater")
            foreign.__name__ = "decky_loader.updater"
            sys.modules["updater"] = foreign

            class Logger:
                def info(self, *args, **kwargs): pass
                def warning(self, *args, **kwargs): pass
                def exception(self, *args, **kwargs): pass

            async def emit(*args, **kwargs): pass

            decky = types.ModuleType("decky")
            decky.DECKY_USER_HOME = str(home)
            decky.logger = Logger()
            decky.emit = emit
            sys.modules["decky"] = decky

            spec = importlib.util.spec_from_file_location(
                "deckyshare_collision_test", plugin_dir / "main.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            manager = module._get_updater()
            assert manager.__class__.__name__ == "UpdateManager"
            assert manager.__class__.__module__ == "_deckyshare_plugin_updater"
            assert sys.modules["updater"] is foreign
            '''
        )
        subprocess.run(
            [sys.executable, "-c", script, str(repo)],
            cwd=repo,
            check=True,
            timeout=15,
        )


if __name__ == "__main__":
    unittest.main()
