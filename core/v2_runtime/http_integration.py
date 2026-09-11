"""HTTP transport boundary for Phoenix Core V2 authentication.

The legacy HTTP handler remains responsible for routing and response formatting.
This module centralises the V2 cookie/session decisions so the handler can adopt
V2 without duplicating authentication logic or falling back to legacy auth.
"""

from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any

from .feature_switch import v2_enabled
from .http_host import build_v2_auth

V2_SESSION_COOKIE = "phoenix_v2_session"
V2_ORGANISATION_COOKIE = "phoenix_v2_organisation"


class V2HttpIntegrationError(RuntimeError):
    """Raised when V2 HTTP session integration cannot establish safe state."""


def cookie_value(cookie_header: str | None, name: str) -> str | None:
    """Read one cookie value without trusting any client-side role information."""
    if not cookie_header:
        return None
    cookies = SimpleCookie()
    cookies.load(cookie_header)
    morsel = cookies.get(name)
    return morsel.value if morsel else None


def build_session_cookie(token: str, *, remember_me: bool = False) -> str:
    """Build the V2 session cookie with HTTP-only and SameSite protections."""
    cookie = f"{V2_SESSION_COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/"
    if remember_me:
        cookie += f"; Max-Age={30 * 24 * 60 * 60}"
    return cookie


def build_organisation_cookie(organisation_id: str) -> str:
    """Build the non-secret organisation context cookie."""
    return f"{V2_ORGANISATION_COOKIE}={organisation_id}; HttpOnly; SameSite=Lax; Path=/"


def clear_v2_cookies() -> tuple[str, str]:
    """Return expiry headers for both V2 session-context cookies."""
    expiry = "; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"
    return (
        f"{V2_SESSION_COOKIE}=;{expiry}",
        f"{V2_ORGANISATION_COOKIE}=;{expiry}",
    )


def authenticate_v2(
    username: str,
    password: str,
    organisation_id: str | None = None,
    remember_me: bool = False,
) -> dict[str, Any]:
    """Authenticate and resolve the destination entirely through Core V2."""
    if not v2_enabled():
        raise V2HttpIntegrationError("Phoenix Core V2 is not enabled.")

    auth = build_v2_auth()
    result = auth.login(username, password, organisation_id)
    data = result.get("data") or {}
    session_id = data.get("session_id")
    token = data.get("token")
    resolved_organisation_id = data.get("organisation_id") or organisation_id

    if not session_id or not token:
        raise V2HttpIntegrationError("Core V2 did not return a usable session.")
    if not resolved_organisation_id:
        raise V2HttpIntegrationError("An authoritative organisation context is required.")

    context = auth.session(str(session_id), str(resolved_organisation_id))
    destination = auth.platform_destination(
        str(session_id), str(resolved_organisation_id)
    )
    destination_data = destination.get("data") or destination
    destination_name = destination_data.get("destination")
    if not destination_name:
        raise V2HttpIntegrationError("Core V2 did not return a platform destination.")

    return {
        "authenticated": True,
        "session_id": str(session_id),
        "token": str(token),
        "organisation_id": str(resolved_organisation_id),
        "context": context,
        "platform": destination_data,
        "destination": destination_name,
        "remember_me": bool(remember_me),
    }


def current_v2_session(
    cookie_header: str | None,
    organisation_id: str | None = None,
) -> dict[str, Any]:
    """Resolve the current V2 session from HTTP cookies and Core context."""
    if not v2_enabled():
        raise V2HttpIntegrationError("Phoenix Core V2 is not enabled.")

    session_id = cookie_value(cookie_header, V2_SESSION_COOKIE)
    organisation = organisation_id or cookie_value(
        cookie_header, V2_ORGANISATION_COOKIE
    )
    if not session_id or not organisation:
        raise V2HttpIntegrationError("Authenticated V2 session context is required.")

    auth = build_v2_auth()
    context = auth.session(session_id, organisation)
    destination = auth.platform_destination(session_id, organisation)
    destination_data = destination.get("data") or destination

    return {
        "session_id": session_id,
        "organisation_id": organisation,
        "context": context,
        "platform": destination_data,
    }


def logout_v2(cookie_header: str | None) -> tuple[bool, tuple[str, str]]:
    """Revoke the V2 session and return cookie-expiry headers."""
    if not v2_enabled():
        raise V2HttpIntegrationError("Phoenix Core V2 is not enabled.")

    session_cookie = cookie_value(cookie_header, V2_SESSION_COOKIE)
    if session_cookie:
        auth = build_v2_auth()
        # The current V2 HTTP facade accepts the authenticated token for revoke.
        auth.logout(session_cookie)

    return True, clear_v2_cookies()
