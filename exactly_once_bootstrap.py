"""Install DeckyShare's v1.1 reliability runtime."""


def install(core):
    from exactly_once import install as install_exactly_once
    from restart_hardening import install as install_restart_hardening
    from rc1_hardening import install as install_rc1_hardening

    install_exactly_once(core)
    install_restart_hardening(core)
    install_rc1_hardening(core)
