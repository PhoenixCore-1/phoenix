"""Host-facing session boundary for the Phoenix Core V2 runtime."""

from __future__ import annotations

from typing import Any

from .feature_switch import v2_enabled
from .http_adapter import V2HttpAdapter


class V2HostSession:
    """Translate login/session operations without exposing V2 internals."""

    def __init__(self, adapter: V2HttpAdapter):
        self.adapter = adapter

    @classmethod
    def from_runtime(cls, runtime_adapter):
        return cls(V2HttpAdapter(runtime_adapter))

    @staticmethod
    def enabled() -> bool:
        return v2_enabled()

    def authenticate(self, username: str, password: str, organisation_id: str | None = None) -> dict[str, Any]:
        return self.adapter.authenticate(
            username=username,
            password=password,
            organisation_id=organisation_id,
        )

    def current_context(self, session_id: str, organisation_id: str) -> dict[str, Any]:
        return self.adapter.current_context(
            session_id=session_id,
            organisation_id=organisation_id,
        )

    def revoke(self, token: str) -> dict[str, Any]:
        return self.adapter.revoke_session(token=token)
