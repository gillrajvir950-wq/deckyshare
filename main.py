import core_main as _core
from exactly_once_bootstrap import install as _install_reliability

_install_reliability(_core)
_core.Handler.server_version = "DeckyShare/1.1.0-rc1"


class Plugin(_core.Plugin):
    pass
