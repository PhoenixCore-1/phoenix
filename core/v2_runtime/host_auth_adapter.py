"""Explicit authentication boundary for the existing Phoenix HTTP host.

This module deliberately contains no legacy authentication fallback. The HTTP
transport may remain in ``core/app.py``, but authentication/session decisions
made through this adapter are delegated to the persistent V2 host middleware.
"""

from __future__ import annotations

from typing import Any

from .feature_switch import v2_enabled
from .http_host_middleware import V2HostMiddleware


class V2HostAuthenticationError(RuntimeError):
    """Raised when V2 authentication cannot be safely adopted."""


def build_host_authentication() -> V2HostMiddleware:
    """Create the host-scoped V2 middleware when V2 is explicitly enabled."""
    if not v2_enabled():
        raise V2HostAuthenticationError("Phoenix Core V2 is not enabled.")
    try:
        return V2HostMiddleware.from_environment()
    except Exception as exc:
        raise V2HostAuthenticationError(
            "Phoenix Core V2 is enabled but could not be initialised."
        ) from exc


def authenticate(
    middleware: V2HostMiddleware,
    username: str,
    password: str,
    organisation_id: str | None = None,
    remember_me: bool = False,
) -> dict[str, Any]:
    """Authenticate through Core V2 and resolve the authoritative destination."""
    return middleware.login(
        username=username,
        password=password,
        organisation_id=organisation_id,
        remember_me=remember_me,
    )


def current_session(
    middleware: V2HostMiddleware,
    session_id: str,
    organisation_id: str,
) -> dict[str, Any]:
    """Resolve session and tenant context through Core V2."""
    return middleware.session(session_id, organisation_id)


def logout(middleware: V2HostMiddleware, token: str) -> dict[str, Any]:
    """Terminate the V2 session through Core V2."""
    return middleware.logout(token)
