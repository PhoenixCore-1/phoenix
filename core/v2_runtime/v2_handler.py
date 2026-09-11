"""Strict V2 request gate for the Phoenix HTTP doorway."""

from __future__ import annotations

from .feature_switch import v2_enabled
from .route_boundary import decide_v2_route


class V2RouteGate:
    """Decide whether an HTTP request may enter legacy handler dispatch."""

    def __init__(self, enabled: bool | None = None):
        self.enabled = v2_enabled() if enabled is None else bool(enabled)

    def decision(self, method: str, path: str) -> str:
        """Return ``v2``, ``public``, ``legacy``, or ``blocked``."""
        if not self.enabled:
            return "legacy"
        decision = decide_v2_route(method, path)
        if decision.code == "V2_AUTH_ROUTE":
            return "v2"
        if decision.code == "TRANSPORT_ROUTE":
            return "public"
        return "blocked"

    def allow_legacy_dispatch(self, method: str, path: str) -> bool:
        """Legacy dispatch is allowed only while V2 is disabled."""
        return self.decision(method, path) == "legacy"
