"""
Phoenix System Platform
Application Runtime Context V1.0.

Carries authenticated Core identity for the current request.

This object does not authenticate, authorize, or access a database.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional


class RuntimeContextError(RuntimeError):
    """Runtime context validation error."""


@dataclass(frozen=True)
class ApplicationRuntimeContext:
    """
    Immutable authenticated runtime context.

    The authenticated user originates from Phoenix Core.
    """

    user: Mapping[str, Any]

    def __post_init__(self):
        if self.user is None:
            raise RuntimeContextError(
                "Authenticated Core user is required."
            )

        if not isinstance(self.user, Mapping):
            raise RuntimeContextError(
                "Runtime context user must be a mapping."
            )

        if self.user.get("user_id") is None:
            raise RuntimeContextError(
                "Authenticated Core user_id is required."
            )

    @property
    def user_id(self) -> int:
        return int(self.user["user_id"])

    @property
    def organisation_id(self) -> Optional[int]:
        value = self.user.get("organisation_id")

        if value is None:
            return None

        return int(value)

    @property
    def identity_scope(self) -> str:
        return str(
            self.user.get("identity_scope") or ""
        ).upper()

    def as_user(self) -> Mapping[str, Any]:
        """
        Return the original authenticated Core user mapping.

        The runtime context does not create or modify identity.
        """
        return self.user
