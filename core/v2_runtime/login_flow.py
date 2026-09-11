"""Shared login orchestration for Phoenix Core V2.

This is the single host-facing authentication flow used by platform landing
pages. It authenticates through Core, resolves authoritative tenant context,
and asks Core for the platform destination. Browser-selected destinations are
never trusted.
"""

from __future__ import annotations

from typing import Any

from .http_host import build_v2_auth


class V2LoginFlowError(RuntimeError):
    """Raised when the shared V2 login flow cannot establish a safe context."""


def login(username: str, password: str, organisation_id: str | None = None) -> dict[str, Any]:
    """Authenticate, resolve context and return Core's authoritative destination."""
    auth = build_v2_auth()
    result = auth.login(username, password, organisation_id)
    data = result.get("data") or {}
    session_id = data.get("session_id")
    token = data.get("token")
    resolved_organisation_id = data.get("organisation_id") or organisation_id

    if not session_id or not token:
        raise V2LoginFlowError("Core authentication did not return a usable session.")
    if not resolved_organisation_id:
        raise V2LoginFlowError("An authoritative organisation context is required.")

    context = auth.session(session_id, resolved_organisation_id)
    destination = auth.platform_destination(session_id, resolved_organisation_id)
    destination_data = destination.get("data") or destination
    resolved_destination = destination_data.get("destination")
    if not resolved_destination:
        raise V2LoginFlowError("Core did not return an authoritative platform destination.")

    return {
        "authenticated": True,
        "session_id": str(session_id),
        "token": token,
        "organisation_id": str(resolved_organisation_id),
        "destination": resolved_destination,
        "context": context,
        "platform": destination_data,
    }
