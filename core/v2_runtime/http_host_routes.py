"""Small route bridge for adopting Core V2 in the existing HTTP host.

This module contains only transport-facing dispatch helpers. The existing
``core/app.py`` handler remains responsible for HTTP response formatting and
all business/module routes. When V2 is enabled, authentication decisions must
come exclusively from the persistent V2 host middleware.
"""

from __future__ import annotations

from typing import Any

from .feature_switch import v2_enabled
from .http_integration import (
    V2HttpIntegration,
    V2HttpIntegrationError,
    build_organisation_cookie,
    build_session_cookie,
    build_token_cookie,
    clear_v2_cookies,
    cookie_value,
)


def login_response(
    integration: V2HttpIntegration,
    *,
    username: str,
    password: str,
    organisation_id: str | None = None,
    remember_me: bool = False,
) -> tuple[dict[str, Any], tuple[str, str, str]]:
    """Authenticate through V2 and return the response payload plus cookies."""
    if not v2_enabled():
        raise V2HttpIntegrationError("Phoenix Core V2 is not enabled.")

    result = integration.login(username, password, organisation_id)
    data = result.get("data") or result
    session_id = data.get("session_id")
    token = data.get("token")
    resolved_organisation_id = data.get("organisation_id") or organisation_id

    if not session_id or not token or not resolved_organisation_id:
        raise V2HttpIntegrationError("Core V2 did not return a complete authenticated context.")

    context = integration.session(str(session_id), str(resolved_organisation_id))
    destination = integration.platform_destination(
        str(session_id), str(resolved_organisation_id)
    )
    destination_data = destination.get("data") or destination
    destination_name = destination_data.get("destination")
    if not destination_name:
        raise V2HttpIntegrationError("Core V2 did not return a platform destination.")

    cookies = (
        build_session_cookie(str(session_id), remember_me=remember_me),
        build_token_cookie(str(token), remember_me=remember_me),
        build_organisation_cookie(str(resolved_organisation_id), remember_me=remember_me),
    )

    return (
        {
            "authenticated": True,
            "session_id": str(session_id),
            "organisation_id": str(resolved_organisation_id),
            "context": context,
            "platform": destination_data,
            "destination": destination_name,
        },
        cookies,
    )


def session_response(
    integration: V2HttpIntegration,
    cookie_header: str | None,
) -> dict[str, Any]:
    """Resolve the authenticated V2 session from the request cookies."""
    if not v2_enabled():
        raise V2HttpIntegrationError("Phoenix Core V2 is not enabled.")

    session_id = cookie_value(cookie_header, "phoenix_v2_session")
    organisation_id = cookie_value(cookie_header, "phoenix_v2_organisation")
    if not session_id or not organisation_id:
        raise V2HttpIntegrationError("Authenticated V2 session context is required.")

    context = integration.session(session_id, organisation_id)
    destination = integration.platform_destination(session_id, organisation_id)
    destination_data = destination.get("data") or destination

    return {
        "authenticated": True,
        "session_id": session_id,
        "organisation_id": organisation_id,
        "context": context,
        "platform": destination_data,
        "destination": destination_data.get("destination"),
    }


def logout_response(
    integration: V2HttpIntegration,
    cookie_header: str | None,
) -> tuple[dict[str, Any], tuple[str, str, str]]:
    """Revoke the V2 token and return expiry cookies."""
    if not v2_enabled():
        raise V2HttpIntegrationError("Phoenix Core V2 is not enabled.")

    token = cookie_value(cookie_header, "phoenix_v2_token")
    if not token:
        return {"ok": True, "revoked": False}, clear_v2_cookies()

    result = integration.logout(token)
    data = result.get("data") or result
    return {"ok": True, "revoked": bool(data.get("revoked", True))}, clear_v2_cookies()
