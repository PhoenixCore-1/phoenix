"""HTTP-facing adapter for the Phoenix Core V2 runtime."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID, uuid4

from .adapter import V2RuntimeAdapter


class V2HttpAdapter:
    """Small HTTP contract boundary over :class:`V2RuntimeAdapter`."""

    def __init__(self, runtime: V2RuntimeAdapter):
        self.runtime = runtime

    @staticmethod
    def _request_id() -> str:
        return str(uuid4())

    @staticmethod
    def _normalise_response(response: Any) -> dict[str, Any]:
        if hasattr(response, "data"):
            return {
                "data": response.data,
                "request_id": getattr(response, "request_id", None),
            }
        if hasattr(response, "__dataclass_fields__"):
            return asdict(response)
        return {"data": response}

    def authenticate(self, *, username: str, password: str, organisation_id: str | None = None) -> dict[str, Any]:
        organisation = UUID(organisation_id) if organisation_id else None
        response = self.runtime.authenticate(
            request_id=self._request_id(),
            username=username,
            password=password,
            organisation_id=organisation,
        )
        return self._normalise_response(response)

    def current_context(self, *, session_id: str, organisation_id: str) -> dict[str, Any]:
        session = UUID(session_id)
        organisation = UUID(organisation_id)
        request_id = self._request_id()
        identity = self.runtime.runtime.api.get_current_identity(
            request_id=request_id, session_id=session, organisation_id=organisation
        )
        user = self.runtime.runtime.api.get_current_user(
            request_id=request_id, session_id=session, organisation_id=organisation
        )
        organisation_response = self.runtime.runtime.api.get_current_organisation(
            request_id=request_id, session_id=session, organisation_id=organisation
        )
        return {
            "authenticated": True,
            "identity": identity.data,
            "user": user.data,
            "organisation": organisation_response.data,
            "request_id": request_id,
        }

    def resolve_platform_destination(self, *, request_id: str, session_id: str, organisation_id: str) -> dict[str, Any]:
        """Ask Core V2 to resolve the authenticated platform destination."""
        response = self.runtime.resolve_platform_destination(
            request_id=request_id,
            session_id=session_id,
            organisation_id=organisation_id,
        )
        return self._normalise_response(response)

    def revoke_session(self, *, token: str) -> dict[str, Any]:
        """Terminate a V2 session through CoreApi."""
        response = self.runtime.revoke_session(
            request_id=self._request_id(),
            token=token,
        )
        return self._normalise_response(response)
