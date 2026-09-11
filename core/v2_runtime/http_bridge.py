"""HTTP-host authentication/session bridge for Phoenix Core V2.

This module contains no HTTP server code. It translates the existing Phoenix
HTTP host's login/session/logout concerns into the authoritative V2 runtime
boundary, keeping cookie formatting and response shaping in the host.
"""

from uuid import UUID, uuid4

from .adapter import V2RuntimeAdapter, V2RuntimeUnavailable


class V2AuthenticationBridge:
    """Translate host authentication operations into Core V2 API calls."""

    def __init__(self, adapter: V2RuntimeAdapter):
        self.adapter = adapter

    @classmethod
    def from_environment(cls):
        return cls(V2RuntimeAdapter.from_environment())

    def authenticate(self, username, password, organisation_id=None):
        """Authenticate and return the authoritative V2 session result."""
        return self.adapter.authenticate(
            request_id=str(uuid4()),
            username=str(username).strip(),
            password=password,
            organisation_id=(UUID(str(organisation_id)) if organisation_id else None),
        )

    def revoke(self, token):
        """Revoke the supplied V2 session token."""
        return self.adapter.revoke_session(
            request_id=str(uuid4()),
            token=token,
        )

    def current_context(self, session_id, organisation_id):
        """Resolve authoritative identity/tenant context through V2."""
        if not session_id or not organisation_id:
            raise ValueError("Both session_id and organisation_id are required.")

        from phoenix_core.api.integration.contracts import IntegrationRequest

        request = IntegrationRequest(
            request_id=str(uuid4()),
            operation="identity.current",
            session_id=UUID(str(session_id)),
            organisation_id=UUID(str(organisation_id)),
            payload={},
        )
        return self.adapter.runtime.integration.handle(request)

    def close(self):
        """Release the V2 runtime resources owned by this bridge."""
        runtime = getattr(self.adapter, "runtime", None)
        if runtime is not None and hasattr(runtime, "close"):
            runtime.close()
