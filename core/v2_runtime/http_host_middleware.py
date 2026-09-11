"""Request-level helpers for safely selecting Phoenix Core V2 authentication.

The legacy HTTP handler remains the transport owner. These helpers provide a
small decision boundary so the handler can opt into V2 without duplicating V2
authentication, session or platform-routing logic.
"""

from __future__ import annotations

from typing import Any

from .feature_switch import v2_enabled
from .http_integration import V2HttpIntegration


class V2HostMiddleware:
    """Host-facing V2 request boundary with one runtime per host lifecycle."""

    def __init__(self, integration: V2HttpIntegration):
        self.integration = integration
        self._closed = False

    @classmethod
    def from_environment(cls) -> "V2HostMiddleware":
        return cls(V2HttpIntegration.from_environment())

    @staticmethod
    def enabled() -> bool:
        return v2_enabled()

    def login(
        self,
        username: str,
        password: str,
        organisation_id: str | None = None,
        remember_me: bool = False,
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("Phoenix Core V2 host middleware is closed.")
        result = self.integration.login(username, password, organisation_id)
        result["remember_me"] = bool(remember_me)
        return result

    def session(self, session_id: str, organisation_id: str) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("Phoenix Core V2 host middleware is closed.")
        return self.integration.session(session_id, organisation_id)

    def platform_destination(self, session_id: str, organisation_id: str) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("Phoenix Core V2 host middleware is closed.")
        return self.integration.platform_destination(session_id, organisation_id)

    def logout(self, token: str) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("Phoenix Core V2 host middleware is closed.")
        return self.integration.logout(token)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.integration.close()
