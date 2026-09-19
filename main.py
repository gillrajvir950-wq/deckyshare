from pathlib import Path
import asyncio
import sys

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

import core_main as _core
from exactly_once_bootstrap import install as _install_reliability
_install_reliability(_core)
_core.Handler.server_version = "DeckyShare/1.1.0-rc.11.23"
_UPDATER = None


def _get_updater():
    global _UPDATER
    if _UPDATER is None:
        # Do not use ``import updater`` here. Decky Loader itself ships a
        # decky_loader.updater module and its frozen runtime can resolve that
        # name before this plugin's updater.py. Load our file explicitly under
        # a unique module name so the two updater implementations can never
        # collide.
        import importlib.util

        updater_path = _PLUGIN_DIR / "updater.py"
        module_name = "_deckyshare_plugin_updater"
        spec = importlib.util.spec_from_file_location(module_name, updater_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load DeckyShare updater module")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        _UPDATER = module.UpdateManager(
            _PLUGIN_DIR, Path(_core.decky.DECKY_USER_HOME)
        )
    return _UPDATER


def _payload_value(payload, key, default=None):
    if isinstance(payload, dict):
        return payload.get(key, default)
    return default


def _include_prereleases(updater, payload=None):
    """RC/dev builds follow prereleases; stable builds stay on stable channel."""
    requested = bool(_payload_value(payload, "include_prerelease", False))
    try:
        current = str(updater.current_version or "")
    except Exception:
        current = ""
    return requested or "-" in current


class Plugin(_core.Plugin):
    async def update_state(self, *args, **kwargs):
        try:
            updater = _get_updater()
            return await asyncio.to_thread(updater.state)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def check_update(self, payload=None, *args, **kwargs):
        force = bool(_payload_value(payload, "force", False))
        try:
            updater = _get_updater()
            include_prerelease = _include_prereleases(updater, payload)
            return await asyncio.to_thread(updater.check, include_prerelease, force)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            _core.decky.logger.exception("DeckyShare update check failed")
            return {"ok": False, "error": f"Update check failed: {exc}"}

    async def install_update(self, payload=None, *args, **kwargs):
        expected_tag = _payload_value(payload, "tag")
        try:
            updater = _get_updater()
            include_prerelease = _include_prereleases(updater, payload)
            return await asyncio.to_thread(updater.prepare_install, expected_tag, include_prerelease)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            _core.decky.logger.exception("DeckyShare update installation failed")
            return {"ok": False, "error": f"Update installation failed: {exc}"}

    async def rollback_update(self, *args, **kwargs):
        try:
            updater = _get_updater()
            return await asyncio.to_thread(updater.rollback)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            _core.decky.logger.exception("DeckyShare update rollback failed")
            return {"ok": False, "error": f"Rollback failed: {exc}"}
