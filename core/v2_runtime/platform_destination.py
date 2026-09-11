"""Authoritative platform destination contract for Phoenix Core V2.

The host may use this contract to route an authenticated session, but it must
not infer platform access from browser state or URL choice. Core remains the
authority for authentication and authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class PlatformDestination(str, Enum):
    SYSTEM_PLATFORM = "SYSTEM_PLATFORM"
    COMPANY_PLATFORM = "COMPANY_PLATFORM"
    USER_PLATFORM = "USER_PLATFORM"


@dataclass(frozen=True)
class PlatformRoute:
    destination: PlatformDestination
    session_id: str
    organisation_id: str
    context: Mapping[str, Any]


def resolve_platform_destination(
    *,
    session_id: str,
    organisation_id: str,
    context: Mapping[str, Any],
) -> PlatformRoute:
    """Resolve a platform route from authoritative Core context.

    This function deliberately accepts only already-resolved Core context. It
    does not inspect cookies, URLs, browser state, or client-supplied roles.
    Until Core exposes an explicit platform entitlement, organisation-level
    users are routed to the User Platform; the System Platform is reserved for
    an explicit Core system-platform capability.
    """
    permissions = frozenset(context.get("permissions", ()) or ())
    entitlements = frozenset(context.get("entitlements", ()) or ())

    if "system.platform.access" in permissions or "system_platform" in entitlements:
        destination = PlatformDestination.SYSTEM_PLATFORM
    elif "company.platform.access" in permissions or "company_platform" in entitlements:
        destination = PlatformDestination.COMPANY_PLATFORM
    else:
        destination = PlatformDestination.USER_PLATFORM

    return PlatformRoute(
        destination=destination,
        session_id=session_id,
        organisation_id=organisation_id,
        context=context,
    )
