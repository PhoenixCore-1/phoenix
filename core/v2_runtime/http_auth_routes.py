"""HTTP-facing authentication/session helpers for Phoenix Core V2.

The legacy HTTP handler remains responsible for transport and response shaping.
This module owns only the V2 authentication decision and authoritative context
resolution. It never falls back to legacy authentication when V2 is enabled.
"""

from uuid import UUID

from .http_bridge import V2AuthenticationBridge


class V2HttpAuth:
    """Small host-facing facade for V2 login, session and logout."""

    def __init__(self, bridge: V2AuthenticationBridge):
        self.bridge = bridge

    @classmethod
    def from_environment(cls):
        return cls(V2AuthenticationBridge.from_environment())

    def login(self, username, password, organisation_id=None):
        return self.bridge.authenticate(username, password, organisation_id)

    def session(self, token, session_id, organisation_id):
        if not token:
            raise ValueError("Authenticated V2 session token is required.")
        if not session_id or not organisation_id:
            raise ValueError("V2 session requires session_id and organisation_id.")
        return self.bridge.current_context(
            UUID(str(session_id)), UUID(str(organisation_id))
        )

    def logout(self, token):
        if not token:
            raise ValueError("Authenticated V2 session token is required.")
        return self.bridge.revoke(token)

    def close(self):
        self.bridge.close()
