import core_main as _core
from exactly_once_bootstrap import install as _install_exactly_once

_install_exactly_once(_core)


class Plugin(_core.Plugin):
    pass
