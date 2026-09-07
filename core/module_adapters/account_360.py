"""Phoenix Core -> Account 360 Module adapter.

Core owns authentication, tenant isolation, permissions, licensing,
navigation, audit and transport. Account 360 owns its account-360 domain
contracts and projections. Core loads the module through this adapter rather
than importing Account 360 internals directly.
"""

from pathlib import Path
from typing import Optional

from module_loader import LoadedModule, load_module


ACCOUNT_360_PACKAGE = "account_360"

_account_360_module: Optional[LoadedModule] = None


def configure_account_360_module(module_path: str | Path) -> LoadedModule:
    """Configure and load the external Phoenix Account 360 module."""
    global _account_360_module
    _account_360_module = load_module(
        ACCOUNT_360_PACKAGE,
        module_path=module_path,
    )
    return _account_360_module


def get_account_360_module() -> LoadedModule:
    """Return the configured Account 360 module."""
    if _account_360_module is None:
        raise RuntimeError(
            "Phoenix Account 360 Module is not configured. "
            "Call configure_account_360_module() first."
        )
    return _account_360_module


def get_account_360_registration() -> dict:
    """Return the public module registration supplied by Account 360."""
    module = get_account_360_module()
    return module.module.registration()


__all__ = [
    "ACCOUNT_360_PACKAGE",
    "configure_account_360_module",
    "get_account_360_module",
    "get_account_360_registration",
]
