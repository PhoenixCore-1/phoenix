"""Explicit configuration gate for Phoenix Core V2 runtime adoption."""

from __future__ import annotations

import os


TRUE_VALUES = frozenset({"1", "true", "yes", "on", "enabled"})


def v2_enabled() -> bool:
    """Return whether the HTTP host is explicitly configured to use V2."""
    return os.getenv("PHOENIX_CORE_V2_ENABLED", "0").strip().lower() in TRUE_VALUES


def v2_configuration() -> dict[str, str | bool | None]:
    """Expose non-secret runtime configuration for diagnostics."""
    return {
        "enabled": v2_enabled(),
        "runtime_path_configured": bool(os.getenv("PHOENIX_CORE_V2_PATH")),
        "database_configured": bool(os.getenv("PHOENIX_CORE_V2_DATABASE")),
    }
