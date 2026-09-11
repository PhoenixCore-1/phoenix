"""HTTP-facing authentication/session helpers for Phoenix Core V2.

The legacy HTTP handler remains responsible for transport and response shaping.
This module owns only the V2 authentication decision and authoritative context
resolution. It never falls back to legacy authentication when V2 is enabled.
"""

from .http_adapter import V2HttpAdapter


class V2HttpAuth:
    """Small host-facing facade for V2 login, session and logout."""

    def __init__(self, adapter: V2HttpAdapter):
        self.adapter = adapter

    @classmethod
    def from_runtime(cls, runtime_adapter):
        return cls(V2HttpAdapter(runtime_adapter))

    def login(self, username, password, organisation_id=None):
        return self.adapter.authenticate(
            username=username,
            password=password,
            organisation_id=organisation_id,
        )

    def session(self, session_id, organisation_id):
        if not session_id or not organisation_id:
            raise ValueError("V2 session requires session_id and organisation_id.")
        return self.adapter.current_context(
            session_id=session_id,
            organisation_id=organisation_id,
        )

    def platform_destination(self, session_id, organisation_id):
        if not session_id or not organisation_id:
            raise ValueError(
                "V2 platform resolution requires session_id and organisation_id."
            )
        return self.adapter.resolve_platform_destination(
            request_id=self.adapter._request_id(),
            session_id=session_id,
            organisation_id=organisation_id,
        )

    def logout(self, token):
        if not token:
            raise ValueError("Authenticated V2 session token is required.")
        return self.adapter.revoke_session(token=token)

    def close(self):
        self.adapter.runtime.close()
