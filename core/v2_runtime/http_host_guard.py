"""Explicit host adoption guard for Phoenix Core V2.

An enabled-but-unavailable V2 runtime is an error, not permission to silently
return to legacy authentication.
"""

from __future__ import annotations

from .feature_switch import v2_enabled
from .http_host_middleware import V2HostMiddleware


class V2HostAdoptionError(RuntimeError):
    """Raised when V2 is enabled but cannot be used safely."""


def require_v2_middleware() -> V2HostMiddleware:
    """Create the persistent V2 host boundary when V2 adoption is enabled."""
    if not v2_enabled():
        raise V2HostAdoptionError("Phoenix Core V2 is not enabled.")
    try:
        return V2HostMiddleware.from_environment()
    except Exception as exc:
        raise V2HostAdoptionError(
            "Phoenix Core V2 is enabled but its HTTP integration is unavailable."
        ) from exc


def should_use_v2() -> bool:
    """Return whether the host must use V2 rather than legacy authentication."""
    return v2_enabled()
