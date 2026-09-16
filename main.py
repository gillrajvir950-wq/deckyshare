from pathlib import Path
import asyncio
import sys

# Decky may load main.py directly without adding the plugin directory to
# sys.path. Add it explicitly so the split RC1 backend modules can import.
_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

import core_main as _core
from exactly_once_bootstrap import install as _install_reliability

_install_reliability(_core)
_core.Handler.server_version = "DeckyShare/1.1.0-rc1"
_UPDATER = None


def _get_updater():
    global _UPDATER
    if _UPDATER is None:
        from updater import UpdateManager
        _UPDATER = UpdateManager(_PLUGIN_DIR, Path(_core.decky.DECKY_USER_HOME))
    return _UPDATER


def _payload_value(payload, key, default=None):
    if isinstance(payload, dict):
        return payload.get(key, default)
    return default


class Plugin(_core.Plugin):
    async def update_state(self, *args, **kwargs):
        try:
            updater = _get_updater()
            return await asyncio.to_thread(updater.state)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def check_update(self, payload=None, *args, **kwargs):
        include_prerelease = bool(_payload_value(payload, "include_prerelease", False))
        force = bool(_payload_value(payload, "force", False))
        try:
            updater = _get_updater()
            return await asyncio.to_thread(updater.check, include_prerelease, force)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            _core.decky.logger.exception("DeckyShare update check failed")
            return {"ok": False, "error": f"Update check failed: {exc}"}

    async def install_update(self, payload=None, *args, **kwargs):
        expected_tag = _payload_value(payload, "tag")
        include_prerelease = bool(_payload_value(payload, "include_prerelease", False))
        try:
            updater = _get_updater()
            return await asyncio.to_thread(updater.install_latest, expected_tag, include_prerelease)
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
