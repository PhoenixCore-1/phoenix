"""Host integration helpers for Phoenix Core V2 authentication.

The HTTP server owns transport, cookies and response formatting. This module
provides the small decision boundary it can call when V2 is enabled, without
accessing the legacy database or authentication functions.
"""

from __future__ import annotations

from typing import Any

from .adapter import V2RuntimeAdapter, V2RuntimeUnavailable
from .feature_switch import v2_enabled
from .http_auth_routes import V2HttpAuth


class V2HostUnavailable(RuntimeError):
    """V2 was explicitly enabled but its runtime could not be initialised."""


def build_v2_auth() -> V2HttpAuth:
    """Build the V2 authentication facade from host environment settings."""
    if not v2_enabled():
        raise V2HostUnavailable("Phoenix Core V2 is not enabled.")
    try:
        adapter = V2RuntimeAdapter.from_environment()
    except V2RuntimeUnavailable as exc:
        raise V2HostUnavailable(str(exc)) from exc
    return V2HttpAuth.from_runtime(adapter)


def v2_login(username: str, password: str, organisation_id: str | None = None) -> dict[str, Any]:
    """Authenticate through V2; never fall back to legacy authentication."""
    return build_v2_auth().login(username, password, organisation_id)


def v2_session(session_id: str, organisation_id: str) -> dict[str, Any]:
    """Resolve the authoritative V2 session context."""
    return build_v2_auth().session(session_id, organisation_id)


def v2_logout(token: str) -> dict[str, Any]:
    """Revoke a V2 session through Core V2."""
    return build_v2_auth().logout(token)
