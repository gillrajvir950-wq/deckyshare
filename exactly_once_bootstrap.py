"""Install DeckyShare's v1.1 exactly-once upload runtime.

Kept separate from main.py so the reliability layer stays reviewable and can be
removed/refactored without touching the established Decky backend surface.
"""


def install(core):
    from exactly_once import install as install_exactly_once
    install_exactly_once(core)
