"""Core-authorized platform entry boundary.

The gateway does not authenticate independently. It resolves the existing V2
session and asks Core V2 which platform the user is authorised to enter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .http_integration import V2HttpIntegration, V2HttpIntegrationError


class PlatformGatewayError(RuntimeError):
    """Base platform gateway error."""


@dataclass(frozen=True)
class PlatformEntry:
    requested: str
    destination: str
    allowed: bool
    status: int
    code: str
    message: str
    context: Mapping[str, Any] | None = None


PLATFORM_PATHS = {
    "/system": "SYSTEM_PLATFORM",
    "/company": "COMPANY_PLATFORM",
    "/user": "USER_PLATFORM",
}


def requested_platform(path: str) -> str | None:
    """Return the platform represented by a request path."""
    return PLATFORM_PATHS.get(path)


def authorize_platform_entry(
    integration: V2HttpIntegration,
    requested: str,
    session_id: str,
    organisation_id: str,
) -> PlatformEntry:
    """Resolve Core's destination and compare it with the requested platform."""
    if requested not in PLATFORM_PATHS.values():
        return PlatformEntry(
            requested=requested,
            destination="",
            allowed=False,
            status=404,
            code="PLATFORM_NOT_FOUND",
            message="Phoenix platform destination not found.",
        )

    if not session_id or not organisation_id:
        return PlatformEntry(
            requested=requested,
            destination="",
            allowed=False,
            status=401,
            code="AUTH_REQUIRED",
            message="Authenticated Core session context is required.",
        )

    try:
        # Core V2 is authoritative for both session validity and destination.
        integration.session(session_id, organisation_id)
        result = integration.platform_destination(session_id, organisation_id)
        destination = result.get("data") or result
        actual = str(destination.get("destination", "")).upper()
    except Exception as exc:
        raise PlatformGatewayError(
            "Phoenix Core could not resolve the platform destination."
        ) from exc

    if actual != requested:
        return PlatformEntry(
            requested=requested,
            destination=actual,
            allowed=False,
            status=403,
            code="PLATFORM_ACCESS_DENIED",
            message="The authenticated Core user is not authorised for this platform.",
            context=destination,
        )

    return PlatformEntry(
        requested=requested,
        destination=actual,
        allowed=True,
        status=200,
        code="PLATFORM_ACCESS_GRANTED",
        message="Platform access authorised by Phoenix Core.",
        context=destination,
    )
