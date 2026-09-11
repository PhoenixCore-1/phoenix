"""Explicit host adoption guard for Phoenix Core V2.

The existing HTTP host can use this boundary to select V2 authentication. The
important invariant is that an enabled-but-unavailable V2 runtime is an error,
not permission to silently return to legacy authentication.
"""

from __future__ import annotations

from .feature_switch import v2_enabled
from .http_integration import V2HttpIntegration, V2HttpIntegrationError


class V2HostAdoptionError(RuntimeError):
    """Raised when V2 is enabled but cannot be used safely."""


def require_v2_integration() -> V2HttpIntegration:
    """Return the V2 HTTP integration when V2 adoption is explicitly enabled."""
    if not v2_enabled():
        raise V2HostAdoptionError("Phoenix Core V2 is not enabled.")
    try:
        return V2HttpIntegration.from_environment()
    except Exception as exc:
        raise V2HostAdoptionError(
            "Phoenix Core V2 is enabled but its HTTP integration is unavailable."
        ) from exc


def should_use_v2() -> bool:
    """Return whether the host must use V2 rather than legacy authentication."""
    return v2_enabled()
