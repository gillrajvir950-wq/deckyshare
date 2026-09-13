from pathlib import Path
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


class Plugin(_core.Plugin):
    pass
