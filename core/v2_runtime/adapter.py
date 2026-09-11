"""Adapter between the Phoenix HTTP host and Phoenix Core V2.

The adapter deliberately imports V2 lazily. The legacy HTTP host can therefore
start independently while V2 is being deployed, but it cannot silently fall
back to legacy business logic when a V2 operation is requested.
"""

import os
import sys
from pathlib import Path
from uuid import UUID

from .contracts import V2Request


class V2RuntimeUnavailable(RuntimeError):
    """Raised when the configured Phoenix Core V2 runtime cannot be loaded."""


class V2RuntimeAdapter:
    """Small, explicit boundary around the authoritative V2 runtime."""

    def __init__(self, runtime):
        self.runtime = runtime

    @classmethod
    def from_environment(cls):
        root = os.getenv("PHOENIX_CORE_V2_PATH")
        if not root:
            raise V2RuntimeUnavailable(
                "PHOENIX_CORE_V2_PATH is not configured."
            )

        path = str(Path(root).expanduser().resolve())
        if path not in sys.path:
            sys.path.insert(0, path)

        try:
            from phoenix_core.runtime import build_runtime
        except ImportError as exc:
            raise V2RuntimeUnavailable(
                "Phoenix Core V2 cannot be imported from PHOENIX_CORE_V2_PATH."
            ) from exc

        database_path = os.getenv("PHOENIX_CORE_V2_DATABASE")
        if not database_path:
            raise V2RuntimeUnavailable(
                "PHOENIX_CORE_V2_DATABASE is not configured."
            )

        try:
            runtime = build_runtime(database_path)
        except Exception as exc:
            raise V2RuntimeUnavailable(
                "Phoenix Core V2 runtime failed to initialise."
            ) from exc

        return cls(runtime)

    def handle(self, request: V2Request):
        """Forward one request through Core V2's integration contract."""
        from phoenix_core.api.integration.contracts import IntegrationRequest

        integration_request = IntegrationRequest(
            request_id=request.request_id,
            operation=request.operation,
            session_id=request.session_id,
            organisation_id=request.organisation_id,
            payload=request.payload,
        )
        return self.runtime.integration.handle(integration_request)

    def authenticate(self, *, request_id, username, password, organisation_id=None):
        """Authenticate through Core V2 without exposing its database."""
        return self.runtime.api.authenticate(
            request_id=request_id,
            username=username,
            password=password,
            organisation_id=(UUID(str(organisation_id)) if organisation_id else None),
        )

    def revoke_session(self, *, request_id, token):
        """Terminate a session through the authoritative V2 API."""
        return self.runtime.api.revoke_session(
            request_id=request_id,
            token=token,
        )
