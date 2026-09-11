"""HTTP transport boundary for Phoenix Core V2 authentication.

The legacy HTTP handler remains responsible for transport and response formatting.
This module centralises the V2 cookie/session decisions so the handler can adopt
V2 without duplicating authentication logic or falling back to legacy auth.
"""

from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any

from .adapter import V2RuntimeAdapter
from .feature_switch import v2_enabled
from .http_auth_routes import V2HttpAuth

V2_SESSION_COOKIE = "phoenix_v2_session"
V2_TOKEN_COOKIE = "phoenix_v2_token"
V2_ORGANISATION_COOKIE = "phoenix_v2_organisation"


class V2HttpIntegrationError(RuntimeError):
    """Raised when V2 HTTP session integration cannot establish safe state."""


class V2HttpIntegration:
    """Persistent HTTP-facing V2 runtime boundary.

    One instance owns one V2 runtime for the lifetime of the HTTP host. Request
    handlers reuse this instance; shutdown calls ``close`` exactly once.
    """

    def __init__(self, auth: V2HttpAuth):
        self.auth = auth
        self._closed = False

    @classmethod
    def from_environment(cls) -> "V2HttpIntegration":
        if not v2_enabled():
            raise V2HttpIntegrationError("Phoenix Core V2 is not enabled.")
        try:
            runtime_adapter = V2RuntimeAdapter.from_environment()
            return cls(V2HttpAuth.from_runtime(runtime_adapter))
        except Exception as exc:
            raise V2HttpIntegrationError(
                "Phoenix Core V2 runtime could not be initialised."
            ) from exc

    def _ensure_open(self) -> None:
        if self._closed:
            raise V2HttpIntegrationError("Phoenix Core V2 HTTP integration is closed.")

    def login(self, username: str, password: str, organisation_id: str | None = None) -> dict[str, Any]:
        self._ensure_open()
        return self.auth.login(username, password, organisation_id)

    def session(self, session_id: str, organisation_id: str) -> dict[str, Any]:
        self._ensure_open()
        return self.auth.session(session_id, organisation_id)

    def platform_destination(self, session_id: str, organisation_id: str) -> dict[str, Any]:
        self._ensure_open()
        return self.auth.platform_destination(session_id, organisation_id)

    def logout(self, token: str) -> dict[str, Any]:
        self._ensure_open()
        return self.auth.logout(token)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.auth.close()


def cookie_value(cookie_header: str | None, name: str) -> str | None:
    """Read one cookie value without trusting any client-side role information."""
    if not cookie_header:
        return None
    cookies = SimpleCookie()
    cookies.load(cookie_header)
    morsel = cookies.get(name)
    return morsel.value if morsel else None


def build_session_cookie(session_id: str, *, remember_me: bool = False) -> str:
    """Build the V2 session-context cookie."""
    cookie = f"{V2_SESSION_COOKIE}={session_id}; HttpOnly; SameSite=Lax; Path=/"
    if remember_me:
        cookie += f"; Max-Age={30 * 24 * 60 * 60}"
    return cookie


def build_token_cookie(token: str, *, remember_me: bool = False) -> str:
    """Build the V2 secret session-token cookie used only for revocation."""
    cookie = f"{V2_TOKEN_COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/"
    if remember_me:
        cookie += f"; Max-Age={30 * 24 * 60 * 60}"
    return cookie


def build_organisation_cookie(organisation_id: str, *, remember_me: bool = False) -> str:
    """Build the non-secret organisation context cookie."""
    cookie = f"{V2_ORGANISATION_COOKIE}={organisation_id}; HttpOnly; SameSite=Lax; Path=/"
    if remember_me:
        cookie += f"; Max-Age={30 * 24 * 60 * 60}"
    return cookie


def clear_v2_cookies() -> tuple[str, str, str]:
    """Return expiry headers for all V2 session-context cookies."""
    expiry = "; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"
    return (
        f"{V2_SESSION_COOKIE}=;{expiry}",
        f"{V2_TOKEN_COOKIE}=;{expiry}",
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

    integration = V2HttpIntegration.from_environment()
    try:
        result = integration.login(username, password, organisation_id)
        data = result.get("data") or {}
        session_id = data.get("session_id")
        token = data.get("token")
        resolved_organisation_id = data.get("organisation_id") or organisation_id
        if not session_id or not token:
            raise V2HttpIntegrationError("Core V2 did not return a usable session.")
        if not resolved_organisation_id:
            raise V2HttpIntegrationError("An authoritative organisation context is required.")
        context = integration.session(str(session_id), str(resolved_organisation_id))
        destination = integration.platform_destination(str(session_id), str(resolved_organisation_id))
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
    finally:
        integration.close()


def current_v2_session(
    cookie_header: str | None,
    organisation_id: str | None = None,
) -> dict[str, Any]:
    """Resolve the current V2 session from HTTP cookies and Core context."""
    if not v2_enabled():
        raise V2HttpIntegrationError("Phoenix Core V2 is not enabled.")
    session_id = cookie_value(cookie_header, V2_SESSION_COOKIE)
    organisation = organisation_id or cookie_value(cookie_header, V2_ORGANISATION_COOKIE)
    if not session_id or not organisation:
        raise V2HttpIntegrationError("Authenticated V2 session context is required.")
    integration = V2HttpIntegration.from_environment()
    try:
        context = integration.session(session_id, organisation)
        destination = integration.platform_destination(session_id, organisation)
        destination_data = destination.get("data") or destination
        return {
            "session_id": session_id,
            "organisation_id": organisation,
            "context": context,
            "platform": destination_data,
        }
    finally:
        integration.close()


def logout_v2(cookie_header: str | None) -> tuple[bool, tuple[str, str, str]]:
    """Revoke the V2 session and return cookie-expiry headers."""
    if not v2_enabled():
        raise V2HttpIntegrationError("Phoenix Core V2 is not enabled.")
    token = cookie_value(cookie_header, V2_TOKEN_COOKIE)
    if token:
        integration = V2HttpIntegration.from_environment()
        try:
            integration.logout(token)
        finally:
            integration.close()
    return True, clear_v2_cookies()
