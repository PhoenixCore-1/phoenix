"""Fail-closed routing policy for the V2 HTTP host.

The existing HTTP handler contains many legacy business routes. Until a route
has an explicit V2 integration, an enabled V2 host must not silently execute it
under the legacy session mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    allowed: bool
    code: str
    message: str


# Routes explicitly owned by the V2 host today. Static UI routes are handled by
# the legacy transport without authentication and therefore are not listed here.
V2_AUTH_ROUTES = frozenset({
    ("GET", "/api/session"),
    ("POST", "/api/login"),
    ("POST", "/api/logout"),
})


def decide_v2_route(method: str, path: str) -> RouteDecision:
    """Return a fail-closed decision for an enabled V2 host."""
    key = (method.upper(), path.split("?", 1)[0])
    if key in V2_AUTH_ROUTES:
        return RouteDecision(True, "V2_AUTH_ROUTE", "Route is owned by Core V2.")
    if path.startswith("/api/"):
        return RouteDecision(
            False,
            "V2_ROUTE_NOT_MIGRATED",
            "This API route is not yet migrated to Core V2.",
        )
    return RouteDecision(True, "TRANSPORT_ROUTE", "Non-API transport route.")
