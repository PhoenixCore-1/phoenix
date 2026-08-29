"""
Phoenix Core module loader.

Provides generic runtime loading for independently packaged
Phoenix modules.

Core does not contain module-specific business rules.
"""

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class LoadedModule:
    code: str
    name: str
    version: str
    package: str
    module: Any


class ModuleLoadError(RuntimeError):
    """Raised when a Phoenix module cannot be loaded or verified."""


def add_module_path(module_path: str | Path) -> Path:
    """
    Add an external Phoenix module root to the Python import path.

    The path is configuration supplied by the host application.
    Core does not contain a hard-coded module location.
    """

    path = Path(module_path).expanduser().resolve()

    if not path.exists():
        raise ModuleLoadError(
            f"Phoenix module path does not exist: {path}"
        )

    if not path.is_dir():
        raise ModuleLoadError(
            f"Phoenix module path is not a directory: {path}"
        )

    path_string = str(path)

    if path_string not in sys.path:
        sys.path.insert(0, path_string)

    return path


def load_module(
    package_name: str,
    *,
    module_path: Optional[str | Path] = None,
) -> LoadedModule:
    """
    Load a Phoenix module by its public package name.

    If module_path is supplied, it is added to the import path
    before loading the module.

    The package must expose:
        __module_code__
        __module_name__
        __version__
    """

    if module_path is not None:
        add_module_path(module_path)

    try:
        module = importlib.import_module(package_name)
    except ImportError as exc:
        raise ModuleLoadError(
            f"Unable to load Phoenix module '{package_name}'"
        ) from exc

    code = getattr(module, "__module_code__", None)
    name = getattr(module, "__module_name__", None)
    version = getattr(module, "__version__", None)

    if not code:
        raise ModuleLoadError(
            f"Module '{package_name}' does not declare __module_code__"
        )

    if not name:
        raise ModuleLoadError(
            f"Module '{package_name}' does not declare __module_name__"
        )

    if not version:
        raise ModuleLoadError(
            f"Module '{package_name}' does not declare __version__"
        )

    return LoadedModule(
        code=str(code),
        name=str(name),
        version=str(version),
        package=package_name,
        module=module,
    )