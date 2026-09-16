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
from updater import UpdateManager, UpdateError

_install_reliability(_core)
_core.Handler.server_version = "DeckyShare/1.1.0-rc1"
_UPDATER = UpdateManager(_PLUGIN_DIR, Path(_core.decky.DECKY_USER_HOME))


def _payload_value(payload, key, default=None):
    if isinstance(payload, dict):
        return payload.get(key, default)
    return default


class Plugin(_core.Plugin):
    async def update_state(self, *args, **kwargs):
        try:
            return await asyncio.to_thread(_UPDATER.state)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def check_update(self, payload=None, *args, **kwargs):
        include_prerelease = bool(_payload_value(payload, "include_prerelease", False))
        force = bool(_payload_value(payload, "force", False))
        try:
            return await asyncio.to_thread(_UPDATER.check, include_prerelease, force)
        except (UpdateError, OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "current": _UPDATER.current_version}
        except Exception as exc:
            _core.decky.logger.exception("DeckyShare update check failed")
            return {"ok": False, "error": f"Update check failed: {exc}", "current": _UPDATER.current_version}

    async def install_update(self, payload=None, *args, **kwargs):
        expected_tag = _payload_value(payload, "tag")
        include_prerelease = bool(_payload_value(payload, "include_prerelease", False))
        try:
            return await asyncio.to_thread(_UPDATER.install_latest, expected_tag, include_prerelease)
        except (UpdateError, OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            _core.decky.logger.exception("DeckyShare update installation failed")
            return {"ok": False, "error": f"Update installation failed: {exc}"}

    async def rollback_update(self, *args, **kwargs):
        try:
            return await asyncio.to_thread(_UPDATER.rollback)
        except (UpdateError, OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            _core.decky.logger.exception("DeckyShare update rollback failed")
            return {"ok": False, "error": f"Rollback failed: {exc}"}
