"""Strict V2 request gate for the Phoenix HTTP doorway."""

from __future__ import annotations

from .feature_switch import v2_enabled
from .route_boundary import classify_route


class V2RouteGate:
    """Decide whether an HTTP request may enter legacy handler dispatch."""

    def __init__(self, enabled: bool | None = None):
        self.enabled = v2_enabled() if enabled is None else bool(enabled)

    def decision(self, method: str, path: str) -> str:
        """Return ``v2``, ``legacy``, or ``blocked`` for the request."""
        if not self.enabled:
            return "legacy"
        route = classify_route(method, path)
        if route in {"public", "v2"}:
            return route
        return "blocked"

    def allow_legacy_dispatch(self, method: str, path: str) -> bool:
        """Legacy dispatch is allowed only while V2 is disabled."""
        return self.decision(method, path) == "legacy"
